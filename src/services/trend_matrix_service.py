"""趋势矩阵服务 - 只读查询，组装板块/分组趋势矩阵行。"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    SectorGroup,
    SectorGroupMember,
    SectorGroupTrendSummary,
    SectorTrendSummary,
    TrackedSector,
)
from src.storage.database import Database

logger = logging.getLogger(__name__)

# ── 板块/分组阶段排序（用于变化状态计算） ──────────────────────────

SECTOR_STAGE_RANK: dict[str, int] = {
    "高位退潮": -1,
    "暂无趋势": 0,
    "短线脉冲": 1,
    "低位启动": 2,
    "轮动补涨": 2,
    "分歧中继": 3,
    "主线延续": 4,
    "主线加强": 5,
}

GROUP_STAGE_RANK: dict[str, int] = {
    "高位退潮": -1,
    "暂无趋势": 0,
    "短线脉冲": 1,
    "低位启动": 2,
    "轮动分化": 3,
    "补涨蔓延": 3,
    "主线扩散": 4,
    "主线共振": 5,
}

# ── 变化状态标签 ─────────────────────────────────────────────────

CHANGE_NEW = "新增"
CHANGE_WARMING = "升温"
CHANGE_STEADY = "延续"
CHANGE_COOLING = "降温"
CHANGE_WEAKENING = "转弱"
CHANGE_MISSING = "缺失"


def compute_change_state(
    current_stage: str | None,
    prior_stage: str | None,
    stage_rank: dict[str, int],
    *,
    has_current: bool,
    has_prior: bool,
) -> str:
    """根据当前和前一阶段计算描述性变化状态。

    Args:
        current_stage: 当前阶段标签
        prior_stage: 前一阶段标签
        stage_rank: 阶段排序字典
        has_current: 是否有当前摘要
        has_prior: 是否有前一摘要

    Returns:
        变化状态标签字符串
    """
    if not has_current:
        return CHANGE_MISSING
    if not has_prior:
        return CHANGE_NEW

    cur_score = stage_rank.get(current_stage, 0)
    prev_score = stage_rank.get(prior_stage, 0)

    if cur_score > prev_score:
        return CHANGE_WARMING
    if cur_score == prev_score:
        return CHANGE_STEADY
    # cur_score < prev_score
    if current_stage in ("暂无趋势", "高位退潮"):
        return CHANGE_WEAKENING
    return CHANGE_COOLING


# ── 数据类 ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class MatrixCell:
    """矩阵单元格：某个日期的趋势状态。"""

    trend_status: str | None
    strength_level: str | None
    output_path: str | None = None


@dataclass(frozen=True)
class SectorMatrixRow:
    """板块矩阵行。"""

    sector_name: str
    sector_code: str | None
    cells: dict[date, MatrixCell]  # end_date -> cell
    latest_date: date | None
    change_state: str


@dataclass(frozen=True)
class GroupMatrixRow:
    """分组矩阵行。"""

    group_name: str
    member_count: int
    cells: dict[date, MatrixCell]
    latest_date: date | None
    change_state: str


@dataclass(frozen=True)
class ExpandedGroupMatrix:
    """展开的分组矩阵：包含分组行 + 成员板块行。"""

    group_row: GroupMatrixRow
    member_rows: list[SectorMatrixRow] = field(default_factory=list)


# ── 服务类 ───────────────────────────────────────────────────────


class TrendMatrixService:
    """只读趋势矩阵服务：查询摘要表、组装矩阵行。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ── 日期选择 ──────────────────────────────────────────────

    @staticmethod
    def resolve_dates(
        summaries: Sequence[SectorTrendSummary | SectorGroupTrendSummary],
        *,
        latest_only: bool = False,
        max_dates: int = 5,
    ) -> list[date]:
        """从摘要列表中提取日期列。

        Args:
            summaries: 摘要记录列表
            latest_only: 仅返回最新日期
            max_dates: 历史窗口最大日期数

        Returns:
            降序排列的日期列表
        """
        seen: set[date] = set()
        dates: list[date] = []
        for s in summaries:
            d = s.end_date
            if d not in seen:
                seen.add(d)
                dates.append(d)
        dates.sort(reverse=True)
        if latest_only:
            return dates[:1]
        return dates[:max_dates]

    # ── 板块矩阵 ─────────────────────────────────────────────

    async def build_sector_matrix(
        self,
        *,
        latest_only: bool = False,
        max_dates: int = 5,
    ) -> tuple[list[SectorMatrixRow], list[date]]:
        """构建板块趋势矩阵。

        Returns:
            (rows, dates) - 矩阵行列表和日期列
        """
        async with self._db.get_session() as session:
            summaries = await self._query_sector_summaries(session)
            tracked = await self._query_tracked_sectors(session)

        dates = self.resolve_dates(summaries, latest_only=latest_only, max_dates=max_dates)

        # 按 sector_id 分组摘要
        by_sector: dict[int, list[SectorTrendSummary]] = {}
        for s in summaries:
            by_sector.setdefault(s.sector_id, []).append(s)

        rows: list[SectorMatrixRow] = []
        for t in tracked:
            sector_summaries = sorted(
                by_sector.get(t.id, []),
                key=lambda s: s.end_date,
                reverse=True,
            )
            row = self._assemble_sector_row(t, sector_summaries, dates)
            rows.append(row)

        return rows, dates

    async def _query_sector_summaries(
        self, session: AsyncSession
    ) -> list[SectorTrendSummary]:
        stmt = (
            select(SectorTrendSummary)
            .order_by(SectorTrendSummary.end_date.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _query_tracked_sectors(
        self, session: AsyncSession
    ) -> list[TrackedSector]:
        stmt = (
            select(TrackedSector)
            .where(TrackedSector.status == "tracked")
            .order_by(TrackedSector.canonical_name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _assemble_sector_row(
        sector: TrackedSector,
        summaries: list[SectorTrendSummary],
        dates: list[date],
    ) -> SectorMatrixRow:
        """组装单个板块矩阵行。"""
        # 构建 date -> summary 映射
        by_date: dict[date, SectorTrendSummary] = {s.end_date: s for s in summaries}

        cells: dict[date, MatrixCell] = {}
        for d in dates:
            s = by_date.get(d)
            if s is not None:
                cells[d] = MatrixCell(
                    trend_status=s.trend_status,
                    strength_level=s.strength_level,
                    output_path=s.output_path,
                )
            else:
                cells[d] = MatrixCell(trend_status=None, strength_level=None)

        latest_date = dates[0] if dates else None
        latest_summary = by_date.get(latest_date) if latest_date else None
        prior_summary = None
        for d in dates[1:]:
            if d in by_date:
                prior_summary = by_date[d]
                break

        change_state = compute_change_state(
            latest_summary.trend_status if latest_summary else None,
            prior_summary.trend_status if prior_summary else None,
            SECTOR_STAGE_RANK,
            has_current=latest_summary is not None,
            has_prior=prior_summary is not None,
        )

        return SectorMatrixRow(
            sector_name=sector.canonical_name,
            sector_code=sector.sector_code,
            cells=cells,
            latest_date=latest_date,
            change_state=change_state,
        )

    # ── 分组矩阵 ─────────────────────────────────────────────

    async def build_group_matrix(
        self,
        *,
        latest_only: bool = False,
        max_dates: int = 5,
    ) -> tuple[list[GroupMatrixRow], list[date]]:
        """构建分组趋势矩阵。

        Returns:
            (rows, dates) - 矩阵行列表和日期列
        """
        async with self._db.get_session() as session:
            summaries = await self._query_group_summaries(session)
            groups = await self._query_active_groups(session)
            member_counts = await self._query_group_member_counts(session)

        dates = self.resolve_dates(summaries, latest_only=latest_only, max_dates=max_dates)

        by_group: dict[int, list[SectorGroupTrendSummary]] = {}
        for s in summaries:
            by_group.setdefault(s.group_id, []).append(s)

        rows: list[GroupMatrixRow] = []
        for g in groups:
            group_summaries = sorted(
                by_group.get(g.id, []),
                key=lambda s: s.end_date,
                reverse=True,
            )
            row = self._assemble_group_row(g, group_summaries, dates, member_counts.get(g.id, 0))
            rows.append(row)

        return rows, dates

    async def _query_group_summaries(
        self, session: AsyncSession
    ) -> list[SectorGroupTrendSummary]:
        stmt = (
            select(SectorGroupTrendSummary)
            .order_by(SectorGroupTrendSummary.end_date.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _query_active_groups(
        self, session: AsyncSession
    ) -> list[SectorGroup]:
        stmt = (
            select(SectorGroup)
            .where(SectorGroup.status == "active")
            .order_by(SectorGroup.canonical_name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def _query_group_member_counts(
        session: AsyncSession,
    ) -> dict[int, int]:
        """查询每个分组的确认成员数量。"""
        from sqlalchemy import func as sql_func

        stmt = (
            select(
                SectorGroupMember.group_id,
                sql_func.count(SectorGroupMember.id),
            )
            .group_by(SectorGroupMember.group_id)
        )
        result = await session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    @staticmethod
    def _assemble_group_row(
        group: SectorGroup,
        summaries: list[SectorGroupTrendSummary],
        dates: list[date],
        member_count: int,
    ) -> GroupMatrixRow:
        """组装单个分组矩阵行。"""
        by_date: dict[date, SectorGroupTrendSummary] = {s.end_date: s for s in summaries}

        cells: dict[date, MatrixCell] = {}
        for d in dates:
            s = by_date.get(d)
            if s is not None:
                cells[d] = MatrixCell(
                    trend_status=s.trend_status,
                    strength_level=s.strength_level,
                    output_path=s.output_path,
                )
            else:
                cells[d] = MatrixCell(trend_status=None, strength_level=None)

        latest_date = dates[0] if dates else None
        latest_summary = by_date.get(latest_date) if latest_date else None
        prior_summary = None
        for d in dates[1:]:
            if d in by_date:
                prior_summary = by_date[d]
                break

        change_state = compute_change_state(
            latest_summary.trend_status if latest_summary else None,
            prior_summary.trend_status if prior_summary else None,
            GROUP_STAGE_RANK,
            has_current=latest_summary is not None,
            has_prior=prior_summary is not None,
        )

        return GroupMatrixRow(
            group_name=group.canonical_name,
            member_count=member_count,
            cells=cells,
            latest_date=latest_date,
            change_state=change_state,
        )

    # ── 分组展开矩阵 ─────────────────────────────────────────

    async def build_expanded_group_matrix(
        self,
        group_name: str,
        *,
        max_dates: int = 5,
    ) -> ExpandedGroupMatrix | None:
        """构建展开的分组矩阵：分组行 + 成员板块行。

        Args:
            group_name: 分组名称
            max_dates: 历史窗口最大日期数

        Returns:
            展开矩阵，或分组不存在时返回 None
        """
        async with self._db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if group is None:
                return None

            members = await self._query_group_members(session, group.id)
            sector_ids = [m.sector_id for m in members]

            group_summaries = await self._query_group_summaries_by_id(session, group.id)
            sector_summaries = await self._query_sector_summaries_by_ids(session, sector_ids)

        # 收集所有日期
        all_summaries = list(group_summaries) + list(sector_summaries)
        dates = self.resolve_dates(all_summaries, latest_only=False, max_dates=max_dates)

        # 组装分组行
        group_row = self._assemble_group_row(
            group,
            sorted(group_summaries, key=lambda s: s.end_date, reverse=True),
            dates,
            len(members),
        )

        # 组装成员板块行
        by_sector: dict[int, list[SectorTrendSummary]] = {}
        for s in sector_summaries:
            by_sector.setdefault(s.sector_id, []).append(s)

        # 构建 sector_id -> TrackedSector 映射
        sector_map: dict[int, TrackedSector] = {}
        for m in members:
            sector_map[m.sector_id] = m.sector  # type: ignore[attr-defined]

        # 构建 sector_id -> relation_type 映射
        relation_map: dict[int, str] = {m.sector_id: m.relation_type for m in members}

        member_rows: list[SectorMatrixRow] = []
        for m in members:
            sector = sector_map.get(m.sector_id)
            if sector is None:
                continue
            s_summaries = sorted(
                by_sector.get(m.sector_id, []),
                key=lambda s: s.end_date,
                reverse=True,
            )
            row = self._assemble_sector_row(sector, s_summaries, dates)
            member_rows.append(row)

        return ExpandedGroupMatrix(group_row=group_row, member_rows=member_rows)

    @staticmethod
    async def _resolve_group(
        session: AsyncSession, name: str
    ) -> SectorGroup | None:
        stmt = select(SectorGroup).where(
            (SectorGroup.canonical_name == name) | (SectorGroup.status == "active")
        ).order_by(SectorGroup.canonical_name)
        # 更精确：先精确匹配
        exact = await session.execute(
            select(SectorGroup).where(SectorGroup.canonical_name == name)
        )
        group = exact.scalar_one_or_none()
        if group is not None:
            return group
        # 尝试别名匹配（aliases 是 JSON 数组字符串）
        import json

        all_groups = await session.execute(
            select(SectorGroup).where(SectorGroup.status == "active")
        )
        for g in all_groups.scalars().all():
            if g.aliases:
                try:
                    aliases = json.loads(g.aliases)
                    if name in aliases:
                        return g
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    @staticmethod
    async def _query_group_members(
        session: AsyncSession, group_id: int
    ) -> list[SectorGroupMember]:
        stmt = (
            select(SectorGroupMember)
            .where(SectorGroupMember.group_id == group_id)
            .order_by(SectorGroupMember.relation_type, SectorGroupMember.sector_id)
        )
        result = await session.execute(stmt)
        members = list(result.scalars().all())
        # 预加载 sector 关系
        for m in members:
            await session.refresh(m, ["sector"])
        return members

    @staticmethod
    async def _query_group_summaries_by_id(
        session: AsyncSession, group_id: int
    ) -> list[SectorGroupTrendSummary]:
        stmt = (
            select(SectorGroupTrendSummary)
            .where(SectorGroupTrendSummary.group_id == group_id)
            .order_by(SectorGroupTrendSummary.end_date.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def _query_sector_summaries_by_ids(
        session: AsyncSession, sector_ids: list[int]
    ) -> list[SectorTrendSummary]:
        if not sector_ids:
            return []
        stmt = (
            select(SectorTrendSummary)
            .where(SectorTrendSummary.sector_id.in_(sector_ids))
            .order_by(SectorTrendSummary.end_date.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
