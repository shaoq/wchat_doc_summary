"""板块分组服务 - 分组 CRUD、成员管理、建议生成与审查、组级趋势更新。"""

import json
import logging
import time as _time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import and_, func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    MarketSector,
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    SectorGroupTrendSummary,
    SectorTrendSummary,
    TrackedSector,
)
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import Database

logger = logging.getLogger(__name__)

GROUP_OUTPUT_DIR = Path("output/sector_groups")


# ------------------------------------------------------------------
# 进度事件
# ------------------------------------------------------------------

@dataclass(frozen=True)
class GroupUpdateProgressEvent:
    """分组更新进度事件。"""

    type: str                                    # batch_start, group_start, member_refresh_start, ...
    group_name: str = ""
    group_index: int = 0
    group_total: int = 0
    stage: str = ""                              # member_refresh, evidence, ai_summary, save
    member_name: str = ""
    action: str = ""                             # updated, skipped, failed, ...
    attempt: int = 0
    max_attempts: int = 0
    retry_delay: float = 0.0
    error: str = ""
    elapsed: float = 0.0
    output_path: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    # 安全诊断元数据（仅 verbose）
    provider: str = ""
    model: str = ""
    base_url_host: str = ""
    exception_type: str = ""

    # 批量上下文（batch_start / batch_done）
    trade_date: str = ""
    target_count: int = 0
    lookback_window: int = 0
    force_mode: bool = False
    refresh_members_mode: str = ""               # default / skip / force
    continue_on_error: bool = True
    # 批量汇总（batch_done）
    success_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    member_refresh_success: int = 0
    member_refresh_failed: int = 0


# 进度回调类型
ProgressCallback = Callable[[GroupUpdateProgressEvent], None]

RELATION_TYPES = (
    "core", "upstream", "downstream", "material",
    "equipment", "catalyst", "related",
)

SUGGESTION_TYPES = ("new_group", "add_members", "update_members")
SUGGESTION_STATUSES = ("pending", "accepted", "ignored", "expired")

# ------------------------------------------------------------------
# 建议生成流水线数据类型
# ------------------------------------------------------------------

THEME_DEFINITIONS: dict[str, list[str]] = {
    "人形机器人链": ["机器人", "机器人概念", "智能机器", "减速器", "丝杠", "灵巧手", "机器视觉", "传感器", "PEEK材料"],
    "光伏产业链": ["光伏", "TOPCon", "BC电池", "HIT电池", "钙钛矿", "HJT电池"],
    "锂电储能链": ["锂电池", "固态电池", "钠电池", "电解液", "盐湖提锂", "锂矿", "充电桩"],
    "军工信息链": ["卫星导航", "军工航天", "海工装备", "大飞机", "军民融合", "国产软件", "信息安全"],
    "医药服务链": ["CRO", "CXO", "仿制药", "生物疫苗", "甲型流感", "基因测序"],
    "消费农业链": ["猪肉", "鸡肉", "白酒", "水产品"],
    "新能源电力链": ["风电", "风能", "核电核能", "地热能", "钒电池", "碳交易"],
}

# 构建 comparison_key → theme_name 索引
_THEME_KEY_INDEX: dict[str, str] = {}
for _theme_name, _members in THEME_DEFINITIONS.items():
    for _member in _members:
        _THEME_KEY_INDEX[SectorIdentity.comparison_key(_member)] = _theme_name


@dataclass(frozen=True)
class CandidateMember:
    """候选成员信息。"""
    sector_id: int
    canonical_name: str
    sector_status: str
    co_occurrence_count: int
    source: str  # "cls_watch" | "market_cache"
    theme_name: str | None = None


@dataclass(frozen=True)
class CandidateCluster:
    """候选聚类。"""
    members: tuple[CandidateMember, ...]
    theme_name: str | None
    source: str  # "cls_watch" | "market_cache"
    is_mixed_theme: bool


@dataclass
class AICleaningResult:
    """AI 语义清洗结果。"""
    accepted: bool
    suggested_group_name: str | None = None
    confidence: float = 0.0
    reason: str | None = None
    accepted_members: list[dict[str, Any]] = field(default_factory=list)
    rejected_members: list[dict[str, Any]] = field(default_factory=list)


class SectorGroupService:
    """板块分组服务。"""

    def __init__(self, db: Database, theme_registry: Any = None) -> None:
        self.db = db
        self._theme_registry = theme_registry

    # ------------------------------------------------------------------
    # 分组 CRUD
    # ------------------------------------------------------------------

    async def create_group(
        self,
        name: str,
        aliases: list[str] | None = None,
        keywords: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """创建板块分组。

        Args:
            name: 分组名称
            aliases: 别名列表
            keywords: 关键词列表
            description: 描述

        Returns:
            创建结果
        """
        canonical = SectorIdentity.normalize(name)

        async with self.db.get_session() as session:
            existing = await self._resolve_group(session, canonical)
            if existing:
                return {
                    "action": "already_exists",
                    "group_id": existing.id,
                    "canonical_name": existing.canonical_name,
                }

            group = SectorGroup(
                canonical_name=canonical,
                aliases=json.dumps(aliases or [], ensure_ascii=False),
                keywords=json.dumps(keywords or [], ensure_ascii=False),
                description=description,
                status="active",
            )
            session.add(group)
            await session.flush()
            await session.refresh(group)

            return {
                "action": "created",
                "group_id": group.id,
                "canonical_name": group.canonical_name,
            }

    async def list_groups(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """列出分组。

        Args:
            status: 状态筛选
            limit: 返回数量

        Returns:
            分组信息列表
        """
        async with self.db.get_session() as session:
            query = select(SectorGroup)

            if status:
                query = query.where(SectorGroup.status == status)
            else:
                query = query.where(SectorGroup.status == "active")

            query = query.order_by(SectorGroup.updated_at.desc()).limit(limit)
            result = await session.execute(query)
            groups = result.scalars().all()

            output = []
            for g in groups:
                member_count = await self._count_members(session, g.id)
                latest_update = await self._get_latest_group_summary_date(session, g.id)
                pending_suggestions = await self._count_pending_suggestions(session, g.id)

                output.append({
                    "id": g.id,
                    "canonical_name": g.canonical_name,
                    "description": g.description,
                    "status": g.status,
                    "member_count": member_count,
                    "latest_update_date": latest_update.isoformat() if latest_update else None,
                    "pending_suggestion_count": pending_suggestions,
                })

            return output

    async def resolve_group(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """按名称或别名解析分组。

        Args:
            name: 分组名称或别名

        Returns:
            分组信息或 None
        """
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, name)
            if not group:
                return None
            return {
                "id": group.id,
                "canonical_name": group.canonical_name,
                "status": group.status,
            }

    async def show_group_detail(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """查看分组详情，包含成员信息。

        Args:
            name: 分组名称

        Returns:
            分组详情或 None
        """
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, name)
            if not group:
                return None

            members = await self._load_group_members(session, group.id)

            aliases: list[str] = []
            if group.aliases:
                try:
                    aliases = json.loads(group.aliases)
                except (json.JSONDecodeError, TypeError):
                    pass

            keywords: list[str] = []
            if group.keywords:
                try:
                    keywords = json.loads(group.keywords)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "id": group.id,
                "canonical_name": group.canonical_name,
                "aliases": aliases,
                "keywords": keywords,
                "description": group.description,
                "status": group.status,
                "members": members,
                "created_at": group.created_at.isoformat() if group.created_at else None,
                "updated_at": group.updated_at.isoformat() if group.updated_at else None,
            }

    # ------------------------------------------------------------------
    # 成员管理
    # ------------------------------------------------------------------

    async def add_member(
        self,
        group_name: str,
        sector_name: str,
        relation_type: str = "related",
        weight: float | None = None,
        source: str = "manual",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """向分组添加成员。

        如果成员已存在则更新元数据。

        Args:
            group_name: 分组名称
            sector_name: 板块名称
            relation_type: 关系类型
            weight: 权重
            source: 来源
            confidence: 置信度

        Returns:
            操作结果
        """
        if relation_type not in RELATION_TYPES:
            return {"action": "error", "error": f"无效的关系类型: {relation_type}"}

        canonical_sector = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return {"action": "error", "error": f"分组 '{group_name}' 不存在"}

            sector = await self._resolve_sector(session, canonical_sector)
            if not sector:
                return {"action": "error", "error": f"板块 '{sector_name}' 不存在"}

            # 检查是否已有成员关系
            result = await session.execute(
                select(SectorGroupMember).where(
                    SectorGroupMember.group_id == group.id,
                    SectorGroupMember.sector_id == sector.id,
                )
            )
            existing_member = result.scalar_one_or_none()

            if existing_member:
                # 更新元数据而非创建重复记录
                existing_member.relation_type = relation_type
                if weight is not None:
                    existing_member.weight = weight
                if source is not None:
                    existing_member.source = source
                if confidence is not None:
                    existing_member.confidence = confidence
                return {
                    "action": "updated",
                    "group_id": group.id,
                    "sector_id": sector.id,
                    "sector_name": sector.canonical_name,
                    "relation_type": relation_type,
                }

            member = SectorGroupMember(
                group_id=group.id,
                sector_id=sector.id,
                relation_type=relation_type,
                weight=weight or 1.0,
                source=source,
                confidence=confidence,
            )
            session.add(member)

        # 运行自动成员证据准备（不生成分组报告）
        try:
            from src.services.evidence_preparation import EvidencePreparationService
            from src.services.market_analyzer import MarketAnalyzer
            prep_service = EvidencePreparationService(self.db)
            market_analyzer = MarketAnalyzer(self.db)
            end_date = market_analyzer.get_latest_trade_date()
            await prep_service.prepare_sector(
                sector.canonical_name, end_date, window_days=10,
            )
        except Exception as e:
            logger.warning("成员证据准备失败: %s", e)

        return {
            "action": "added",
            "group_id": group.id,
            "sector_id": sector.id,
            "sector_name": sector.canonical_name,
            "relation_type": relation_type,
        }

    # ------------------------------------------------------------------
    # 建议生成
    # ------------------------------------------------------------------

    async def generate_suggestions(
        self,
        days: int = 10,
        *,
        ai_processor: Any = None,
    ) -> dict[str, Any]:
        """生成分组建议。

        四段流水线：收集输入 → 规则候选 → 主题约束 + AI 清洗 → 建议落库。

        Args:
            days: 回看天数
            ai_processor: 可选 AI 处理器，用于语义清洗

        Returns:
            生成结果统计
        """
        cutoff_date = date.today() - timedelta(days=days)

        async with self.db.get_session() as session:
            # 获取 tracked 和 candidate 板块（排除 ignored 和 inactive）
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.status.in_(["tracked", "candidate"])
                )
            )
            eligible_sectors = list(result.scalars().all())

            # 获取已有分组
            result = await session.execute(
                select(SectorGroup).where(SectorGroup.status == "active")
            )
            existing_groups = list(result.scalars().all())

            # 获取已有成员
            result = await session.execute(select(SectorGroupMember))
            existing_members = list(result.scalars().all())

            # 获取已有 pending 建议
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.status == "pending"
                )
            )
            pending_suggestions = list(result.scalars().all())

        # 构建共现图（优先 CLS 看盘板块标签，回退到行情缓存）
        co_occurrence, co_source = await self._build_co_occurrence(cutoff_date)

        # 生成建议
        new_count = 0
        add_count = 0
        refresh_count = 0

        for group in existing_groups:
            suggestions = await self._suggest_for_existing_group(
                group=group,
                eligible_sectors=eligible_sectors,
                existing_members=existing_members,
                co_occurrence=co_occurrence,
                co_source=co_source,
                pending_suggestions=pending_suggestions,
                days=days,
            )
            add_count += suggestions["add_members"]
            refresh_count += suggestions["refreshed"]

        # 检测新分组机会
        new_group_suggestions = await self._suggest_new_groups(
            eligible_sectors=eligible_sectors,
            existing_groups=existing_groups,
            existing_members=existing_members,
            co_occurrence=co_occurrence,
            co_source=co_source,
            pending_suggestions=pending_suggestions,
            days=days,
            ai_processor=ai_processor,
        )
        new_count = new_group_suggestions["new_groups"]

        return {
            "new_group_suggestions": new_count,
            "add_member_suggestions": add_count,
            "refreshed_suggestions": refresh_count,
        }

    async def list_suggestions(
        self,
        status: str | None = "pending",
        suggestion_type: str | None = None,
        group_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出建议。

        Args:
            status: 状态筛选
            suggestion_type: 建议类型筛选
            group_name: 目标分组筛选

        Returns:
            建议列表
        """
        async with self.db.get_session() as session:
            query = select(SectorGroupSuggestion)

            if status:
                query = query.where(SectorGroupSuggestion.status == status)
            if suggestion_type:
                query = query.where(SectorGroupSuggestion.suggestion_type == suggestion_type)

            if group_name:
                group = await self._resolve_group(session, group_name)
                if group:
                    query = query.where(SectorGroupSuggestion.target_group_id == group.id)

            query = query.order_by(SectorGroupSuggestion.confidence.desc().nullslast())
            result = await session.execute(query)
            suggestions = result.scalars().all()
            active_groups: list[SectorGroup] = []
            if status in (None, "pending"):
                result = await session.execute(
                    select(SectorGroup).where(SectorGroup.status == "active")
                )
                active_groups = list(result.scalars().all())

            output = []
            for s in suggestions:
                if (
                    s.status == "pending"
                    and s.suggestion_type == "new_group"
                    and s.suggested_group_name
                    and self._find_existing_group_by_name(active_groups, s.suggested_group_name)
                ):
                    continue

                members = await self._load_suggestion_members(session, s.id)
                group_name_resolved = None
                if s.target_group_id:
                    grp = await session.execute(
                        select(SectorGroup).where(SectorGroup.id == s.target_group_id)
                    )
                    grp_obj = grp.scalar_one_or_none()
                    if grp_obj:
                        group_name_resolved = grp_obj.canonical_name

                output.append({
                    "id": s.id,
                    "suggestion_type": s.suggestion_type,
                    "target_group_id": s.target_group_id,
                    "target_group_name": group_name_resolved,
                    "suggested_group_name": s.suggested_group_name,
                    "status": s.status,
                    "confidence": s.confidence,
                    "reason": s.reason,
                    "members": members,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                })

            return output

    async def accept_suggestion(
        self,
        suggestion_id: int,
        include_sectors: list[str] | None = None,
        exclude_sectors: list[str] | None = None,
        keep_status: bool = False,
    ) -> dict[str, Any]:
        """接受建议。

        Args:
            suggestion_id: 建议 ID
            include_sectors: 仅接受这些板块（部分接受）
            exclude_sectors: 排除这些板块
            keep_status: 保持板块原状态，不提升 candidate 为 tracked

        Returns:
            接受结果
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.id == suggestion_id
                )
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}，无法接受"}

            # 加载建议成员
            result = await session.execute(
                select(SectorGroupSuggestionMember).where(
                    SectorGroupSuggestionMember.suggestion_id == suggestion_id
                )
            )
            suggestion_members = list(result.scalars().all())

            # 确定目标分组
            group_id = suggestion.target_group_id
            if suggestion.suggestion_type == "new_group" and not group_id:
                group = SectorGroup(
                    canonical_name=SectorIdentity.normalize(
                        suggestion.suggested_group_name or "未命名分组"
                    ),
                    status="active",
                )
                session.add(group)
                await session.flush()
                await session.refresh(group)
                group_id = group.id

            if not group_id:
                return {"action": "error", "error": "无法确定目标分组"}

            # 筛选成员
            accepted_members = []
            for sm in suggestion_members:
                sector = await session.execute(
                    select(TrackedSector).where(TrackedSector.id == sm.sector_id)
                )
                sector_obj = sector.scalar_one_or_none()
                if not sector_obj:
                    continue

                sector_name = sector_obj.canonical_name

                if include_sectors:
                    if sector_name not in include_sectors and sector_obj.canonical_name not in include_sectors:
                        continue
                if exclude_sectors:
                    if sector_name in exclude_sectors or sector_obj.canonical_name in exclude_sectors:
                        continue

                # 检查是否已是成员
                existing = await session.execute(
                    select(SectorGroupMember).where(
                        SectorGroupMember.group_id == group_id,
                        SectorGroupMember.sector_id == sm.sector_id,
                    )
                )
                existing_member = existing.scalar_one_or_none()

                if existing_member:
                    # 更新已有成员
                    if sm.suggested_relation_type:
                        existing_member.relation_type = sm.suggested_relation_type
                    if sm.suggested_weight is not None:
                        existing_member.weight = sm.suggested_weight
                else:
                    # 创建新成员
                    member = SectorGroupMember(
                        group_id=group_id,
                        sector_id=sm.sector_id,
                        relation_type=sm.suggested_relation_type or "related",
                        weight=sm.suggested_weight or 1.0,
                        source="suggestion",
                        confidence=sm.confidence,
                    )
                    session.add(member)

                # 提升 candidate 为 tracked
                if not keep_status and sector_obj.status == "candidate":
                    sector_obj.status = "tracked"

                accepted_members.append(sector_name)

            suggestion.status = "accepted"

        # 对接受的成员运行证据准备
        if accepted_members:
            try:
                from src.services.evidence_preparation import EvidencePreparationService
                from src.services.market_analyzer import MarketAnalyzer
                prep_service = EvidencePreparationService(self.db)
                market_analyzer = MarketAnalyzer(self.db)
                end_date = market_analyzer.get_latest_trade_date()
                for member_name in accepted_members:
                    try:
                        await prep_service.prepare_sector(
                            member_name, end_date, window_days=10,
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("接受建议后证据准备失败: %s", e)

        return {
                "action": "accepted",
                "suggestion_id": suggestion_id,
                "group_id": group_id,
                "accepted_members": accepted_members,
            }

    async def ignore_suggestion(
        self,
        suggestion_id: int,
    ) -> dict[str, Any]:
        """忽略建议。

        Args:
            suggestion_id: 建议 ID

        Returns:
            操作结果
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.id == suggestion_id
                )
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}，无法忽略"}

            suggestion.status = "ignored"

            return {
                "action": "ignored",
                "suggestion_id": suggestion_id,
            }

    # ------------------------------------------------------------------
    # 组级趋势更新
    # ------------------------------------------------------------------

    async def update_group_trend(
        self,
        group_name: str,
        *,
        ai_processor: Any = None,
        force: bool = False,
        no_refresh_members: bool = False,
        force_refresh_members: bool = False,
        days: int = 10,
        continue_on_error: bool = True,
        progress_callback: ProgressCallback | None = None,
        group_index: int = 0,
        group_total: int = 0,
        report_date: date | None = None,
    ) -> dict[str, Any]:
        """更新分组趋势。

        Args:
            group_name: 分组名称
            ai_processor: AI 处理器
            force: 强制重新生成
            no_refresh_members: 跳过成员刷新
            force_refresh_members: 强制刷新所有成员
            days: 回看窗口天数
            continue_on_error: 成员刷新失败后继续
            progress_callback: 进度回调
            group_index: 当前分组序号（批量时）
            group_total: 总分组数（批量时）
            report_date: 报告日期（默认最近交易日）

        Returns:
            更新结果
        """
        from src.services.sector_trend_service import SectorTrendAnalyzer
        from src.services.trade_calendar import get_previous_trade_date, is_trade_day

        def _emit(event_type: str, **kwargs: Any) -> None:
            if progress_callback is not None:
                progress_callback(GroupUpdateProgressEvent(
                    type=event_type,
                    group_name=group_name,
                    group_index=group_index,
                    group_total=group_total,
                    **kwargs,
                ))

        end_date = report_date or self._get_latest_trade_date()

        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return {"action": "error", "error": f"分组 '{group_name}' 不存在"}

            group_id = group.id
            group_canonical = group.canonical_name

        # 检查已有报告
        if not force:
            existing_summary = await self._get_latest_group_summary(group_id)
            if existing_summary and existing_summary.end_date == end_date:
                _emit("group_skipped", output_path=existing_summary.output_path or "")
                return {
                    "action": "skipped",
                    "group_name": group_canonical,
                    "reason": "今日已更新",
                    "output_path": existing_summary.output_path,
                }

        # 加载成员
        async with self.db.get_session() as session:
            members = await self._load_group_members(session, group_id)

        # 成员刷新
        refresh_results: list[dict[str, Any]] = []
        if not no_refresh_members and ai_processor:
            analyzer = SectorTrendAnalyzer(self.db)
            for member in members:
                sector_status = member.get("sector_status")
                member_name = member["sector_name"]
                refresh_start = _time.perf_counter()

                if sector_status == "candidate":
                    refresh_results.append({
                        "sector_name": member_name,
                        "action": "skipped_candidate",
                    })
                    _emit("member_refresh_skip", member_name=member_name,
                          action="skipped_candidate", elapsed=_time.perf_counter() - refresh_start)
                    continue

                if sector_status not in ("tracked",):
                    refresh_results.append({
                        "sector_name": member_name,
                        "action": "skipped_status",
                    })
                    _emit("member_refresh_skip", member_name=member_name,
                          action="skipped_status", elapsed=_time.perf_counter() - refresh_start)
                    continue

                # 检查是否已有当日报告
                if not force_refresh_members:
                    has_today = await self._sector_has_report(member["sector_id"], end_date)
                    if has_today:
                        refresh_results.append({
                            "sector_name": member_name,
                            "action": "skipped_has_report",
                        })
                        _emit("member_refresh_skip", member_name=member_name,
                              action="skipped_has_report", elapsed=_time.perf_counter() - refresh_start)
                        continue

                _emit("member_refresh_start", member_name=member_name, stage="member_refresh")
                try:
                    # 桥接成员板块内部阶段事件到 GroupUpdateProgressEvent
                    def _member_stage_cb(stage: str, detail: str) -> None:
                        _emit("member_stage", member_name=member_name,
                              stage=stage, action=detail)

                    update_result = await analyzer.update_sector_trend(
                        member_name,
                        days=days,
                        ai_processor=ai_processor,
                        force=force_refresh_members,
                        progress_callback=_member_stage_cb,
                        report_date=end_date,
                    )
                    refresh_results.append(update_result)
                    _emit("member_refresh_done", member_name=member_name,
                          action=update_result.get("action", "updated"),
                          elapsed=_time.perf_counter() - refresh_start)
                except Exception as e:
                    elapsed = _time.perf_counter() - refresh_start
                    logger.error("刷新成员 %s 失败: %s", member_name, e)
                    refresh_results.append({
                        "action": "failed",
                        "sector_name": member_name,
                        "error": str(e),
                    })
                    _emit("member_refresh_failed", member_name=member_name,
                          error=str(e), elapsed=elapsed, stage="member_refresh")
                    if not continue_on_error:
                        break

        # 运行分组证据准备
        group_prep_result = None
        try:
            from src.services.evidence_preparation import EvidencePreparationService
            prep_service = EvidencePreparationService(self.db)
            group_prep_result = await prep_service.prepare_group(
                group.canonical_name, end_date, days,
            )
        except Exception as e:
            logger.warning("分组证据准备失败: %s", e)

        # 收集组级证据
        _emit("group_evidence_start", stage="evidence")
        evidence_start = _time.perf_counter()
        evidence = await self._collect_group_evidence(group_id, end_date, days)
        if group_prep_result is not None:
            evidence["preparation_summary"] = group_prep_result.to_dict()
            evidence["preparation_diagnostics"] = group_prep_result.diagnostics.to_dict()
            evidence["member_evidence_quality"] = self._build_member_evidence_quality(
                evidence.get("member_summaries", []),
                group_prep_result,
                end_date,
            )
        _emit("group_evidence_done", stage="evidence", elapsed=_time.perf_counter() - evidence_start)

        # 成员新鲜度
        member_freshness = await self._calculate_member_freshness(
            group_id, end_date, members
        )

        # AI 生成组级报告
        if ai_processor is None:
            return {
                "action": "no_ai_processor",
                "group_name": group_canonical,
                "evidence": evidence,
                "member_refresh_results": refresh_results,
            }

        _emit("group_ai_start", stage="ai_summary")
        ai_start = _time.perf_counter()
        try:
            # 桥接 AI retry 诊断事件
            def _ai_retry_cb(diag: dict) -> None:
                _emit("api_retry", stage="ai_summary", error=diag.get("error", ""),
                      attempt=diag.get("attempt", 0),
                      max_attempts=diag.get("max_attempts", 0),
                      retry_delay=diag.get("retry_delay", 0.0),
                      provider=diag.get("provider", ""),
                      model=diag.get("model", ""),
                      base_url_host=diag.get("base_url_host", ""),
                      exception_type=diag.get("exception_type", ""))

            content, labels = await ai_processor.generate_sector_group_trend_summary(
                group_name=group_canonical,
                evidence=evidence,
                member_freshness=member_freshness,
                end_date=end_date.isoformat(),
                window_days=days,
                retry_callback=_ai_retry_cb,
            )
            _emit("group_ai_done", stage="ai_summary", elapsed=_time.perf_counter() - ai_start)
        except Exception as e:
            _emit("group_failed", stage="ai_summary", error=str(e),
                  elapsed=_time.perf_counter() - ai_start)
            return {
                "action": "failed",
                "group_name": group_canonical,
                "stage": "ai_summary",
                "error": str(e),
                "member_refresh_results": refresh_results,
            }

        summary = await self._save_group_trend_summary(
            group_id=group_id,
            group_name=group_canonical,
            end_date=end_date,
            window_days=days,
            content=content,
            trend_status=labels.get("trend_status"),
            strength_level=labels.get("strength_level"),
            action_bias=labels.get("action_bias"),
            judgement=labels.get("judgement"),
            evidence_json=json.dumps(evidence, ensure_ascii=False),
            member_freshness_json=json.dumps(member_freshness, ensure_ascii=False),
        )

        _emit("group_saved", stage="save", output_path=summary.output_path or "",
              labels={k: v for k, v in labels.items() if isinstance(v, str)})

        return {
            "action": "updated",
            "group_name": group_canonical,
            "end_date": end_date.isoformat(),
            "output_path": summary.output_path,
            "trend_status": labels.get("trend_status"),
            "strength_level": labels.get("strength_level"),
            "action_bias": labels.get("action_bias"),
            "member_refresh_results": refresh_results,
        }

    async def update_all_group_trends(
        self,
        *,
        ai_processor: Any = None,
        force: bool = False,
        no_refresh_members: bool = False,
        force_refresh_members: bool = False,
        days: int = 10,
        continue_on_error: bool = True,
        limit: int | None = None,
        progress_callback: ProgressCallback | None = None,
        report_date: date | None = None,
    ) -> dict[str, Any]:
        """批量更新所有活跃分组趋势。

        Args:
            ai_processor: AI 处理器
            force: 强制重新生成
            no_refresh_members: 跳过成员刷新
            force_refresh_members: 强制刷新所有成员
            days: 回看窗口天数
            continue_on_error: 错误时继续
            limit: 最大更新数量
            progress_callback: 进度回调
            report_date: 报告日期（默认最近交易日）

        Returns:
            批量更新结果
        """
        end_date = report_date or self._get_latest_trade_date()

        # 批量共享准备：对共享窗口运行一次 CLS 修复
        try:
            from src.services.evidence_preparation import EvidencePreparationService
            prep_service = EvidencePreparationService(self.db)
            await prep_service.prepare_window_shared(end_date, days)
        except Exception as e:
            logger.warning("批量分组共享准备失败: %s", e)

        async with self.db.get_session() as session:
            query = select(SectorGroup).where(
                SectorGroup.status == "active"
            ).order_by(SectorGroup.updated_at.asc())
            if limit:
                query = query.limit(limit)
            result = await session.execute(query)
            groups = list(result.scalars().all())

        total = len(groups)

        # 确定成员刷新模式描述
        if no_refresh_members:
            refresh_mode = "skip"
        elif force_refresh_members:
            refresh_mode = "force"
        else:
            refresh_mode = "default"

        # 发射 batch_start
        if progress_callback is not None:
            progress_callback(GroupUpdateProgressEvent(
                type="batch_start",
                trade_date=end_date.isoformat(),
                target_count=total,
                lookback_window=days,
                force_mode=force,
                refresh_members_mode=refresh_mode,
                continue_on_error=continue_on_error,
            ))

        batch_start = _time.perf_counter()
        results: list[dict[str, Any]] = []
        success = 0
        skipped = 0
        failed = 0
        member_refresh_success = 0
        member_refresh_failed = 0

        for i, group in enumerate(groups, 1):
            # 发射 group_start
            if progress_callback is not None:
                progress_callback(GroupUpdateProgressEvent(
                    type="group_start",
                    group_name=group.canonical_name,
                    group_index=i,
                    group_total=total,
                ))

            group_start = _time.perf_counter()
            try:
                update_result = await self.update_group_trend(
                    group.canonical_name,
                    ai_processor=ai_processor,
                    force=force,
                    no_refresh_members=no_refresh_members,
                    force_refresh_members=force_refresh_members,
                    days=days,
                    continue_on_error=continue_on_error,
                    progress_callback=progress_callback,
                    group_index=i,
                    group_total=total,
                    report_date=report_date,
                )
                results.append(update_result)

                action = update_result.get("action")
                if action == "updated":
                    success += 1
                elif action == "skipped":
                    skipped += 1
                else:
                    skipped += 1

                # 统计成员刷新
                for mr in update_result.get("member_refresh_results", []):
                    if mr.get("action") == "updated":
                        member_refresh_success += 1
                    elif mr.get("action") == "failed":
                        member_refresh_failed += 1

                # 发射 group 完成事件
                if progress_callback is not None:
                    progress_callback(GroupUpdateProgressEvent(
                        type="group_done" if action != "failed" else "group_failed",
                        group_name=group.canonical_name,
                        group_index=i,
                        group_total=total,
                        action=action or "",
                        elapsed=_time.perf_counter() - group_start,
                        output_path=update_result.get("output_path", "") or "",
                        labels={
                            k: str(v)
                            for k, v in update_result.items()
                            if k in ("trend_status", "strength_level", "action_bias") and v
                        },
                        error=update_result.get("error", "") or "",
                    ))

            except Exception as e:
                logger.error("更新分组 %s 失败: %s", group.canonical_name, e)
                failed += 1
                results.append({
                    "action": "failed",
                    "group_name": group.canonical_name,
                    "error": str(e),
                })
                if progress_callback is not None:
                    progress_callback(GroupUpdateProgressEvent(
                        type="group_failed",
                        group_name=group.canonical_name,
                        group_index=i,
                        group_total=total,
                        action="failed",
                        error=str(e),
                        elapsed=_time.perf_counter() - group_start,
                    ))
                if not continue_on_error:
                    break

        batch_elapsed = _time.perf_counter() - batch_start

        # 发射 batch_done
        if progress_callback is not None:
            progress_callback(GroupUpdateProgressEvent(
                type="batch_done",
                success_count=success,
                skipped_count=skipped,
                failed_count=failed,
                member_refresh_success=member_refresh_success,
                member_refresh_failed=member_refresh_failed,
                elapsed=batch_elapsed,
                target_count=total,
            ))

        return {
            "total": total,
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "member_refresh_success": member_refresh_success,
            "member_refresh_failed": member_refresh_failed,
            "results": results,
        }

    # ------------------------------------------------------------------
    # 查看与历史
    # ------------------------------------------------------------------

    async def show_latest_group_report(
        self,
        group_name: str,
    ) -> dict[str, Any] | None:
        """查看分组最新趋势报告。"""
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return None

            summary = await self._get_latest_group_summary(group.id)
            if not summary:
                return {
                    "group_name": group.canonical_name,
                    "status": group.status,
                    "has_summary": False,
                }

            return {
                "group_name": group.canonical_name,
                "status": group.status,
                "has_summary": True,
                "end_date": summary.end_date.isoformat() if summary.end_date else None,
                "trend_status": summary.trend_status,
                "strength_level": summary.strength_level,
                "action_bias": summary.action_bias,
                "content": summary.content,
                "output_path": summary.output_path,
                "member_freshness": summary.member_freshness_json,
            }

    async def group_history(
        self,
        group_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """查看分组趋势历史。"""
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return []

            result = await session.execute(
                select(SectorGroupTrendSummary)
                .where(SectorGroupTrendSummary.group_id == group.id)
                .order_by(SectorGroupTrendSummary.end_date.desc())
                .limit(limit)
            )
            summaries = result.scalars().all()

        return [
            {
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "trend_status": s.trend_status,
                "strength_level": s.strength_level,
                "action_bias": s.action_bias,
                "output_path": s.output_path,
            }
            for s in summaries
        ]

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

    async def _resolve_group(
        self,
        session: AsyncSession,
        name: str,
    ) -> SectorGroup | None:
        """按名称或别名解析分组。"""
        canonical = SectorIdentity.normalize(name)

        # 先按规范名精确匹配
        result = await session.execute(
            select(SectorGroup).where(
                SectorGroup.canonical_name == canonical
            )
        )
        group = result.scalar_one_or_none()
        if group:
            return group

        # 按别名匹配
        result = await session.execute(select(SectorGroup))
        all_groups = result.scalars().all()

        name_key = SectorIdentity.comparison_key(name)
        for g in all_groups:
            if g.aliases:
                try:
                    aliases = json.loads(g.aliases)
                    for alias in aliases:
                        if SectorIdentity.comparison_key(alias) == name_key:
                            return g
                except (json.JSONDecodeError, TypeError):
                    pass
            if g.keywords:
                try:
                    keywords = json.loads(g.keywords)
                    for kw in keywords:
                        if SectorIdentity.comparison_key(kw) == name_key:
                            return g
                except (json.JSONDecodeError, TypeError):
                    pass

        return None

    async def _resolve_sector(
        self,
        session: AsyncSession,
        name: str,
    ) -> TrackedSector | None:
        """按名称解析板块。"""
        canonical = SectorIdentity.normalize(name)
        result = await session.execute(
            select(TrackedSector).where(
                TrackedSector.canonical_name == canonical
            )
        )
        return result.scalar_one_or_none()

    async def _count_members(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> int:
        """统计分组成员数量。"""
        result = await session.execute(
            select(sql_func.count(SectorGroupMember.id)).where(
                SectorGroupMember.group_id == group_id
            )
        )
        return result.scalar() or 0

    async def _count_pending_suggestions(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> int:
        """统计分组待处理建议数量。"""
        result = await session.execute(
            select(sql_func.count(SectorGroupSuggestion.id)).where(
                SectorGroupSuggestion.target_group_id == group_id,
                SectorGroupSuggestion.status == "pending",
            )
        )
        return result.scalar() or 0

    async def _get_latest_group_summary_date(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> date | None:
        """获取分组最新趋势报告日期。"""
        result = await session.execute(
            select(sql_func.max(SectorGroupTrendSummary.end_date)).where(
                SectorGroupTrendSummary.group_id == group_id
            )
        )
        return result.scalar()

    async def _load_group_members(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> list[dict[str, Any]]:
        """加载分组成员详情。"""
        result = await session.execute(
            select(SectorGroupMember, TrackedSector)
            .join(TrackedSector, SectorGroupMember.sector_id == TrackedSector.id)
            .where(SectorGroupMember.group_id == group_id)
            .order_by(SectorGroupMember.weight.desc().nullslast())
        )
        rows = result.all()

        members = []
        for member, sector in rows:
            # 获取板块最新趋势报告日期
            latest_summary_result = await session.execute(
                select(sql_func.max(SectorTrendSummary.end_date)).where(
                    SectorTrendSummary.sector_id == sector.id
                )
            )
            latest_summary_date = latest_summary_result.scalar()

            members.append({
                "sector_id": sector.id,
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "relation_type": member.relation_type,
                "weight": member.weight,
                "source": member.source,
                "confidence": member.confidence,
                "last_seen_date": sector.last_seen_date.isoformat() if sector.last_seen_date else None,
                "last_updated_date": sector.last_updated_date.isoformat() if sector.last_updated_date else None,
                "latest_summary_date": latest_summary_date.isoformat() if latest_summary_date else None,
            })

        return members

    async def _load_suggestion_members(
        self,
        session: AsyncSession,
        suggestion_id: int,
    ) -> list[dict[str, Any]]:
        """加载建议成员详情。"""
        result = await session.execute(
            select(SectorGroupSuggestionMember, TrackedSector)
            .join(TrackedSector, SectorGroupSuggestionMember.sector_id == TrackedSector.id)
            .where(SectorGroupSuggestionMember.suggestion_id == suggestion_id)
        )
        rows = result.all()

        return [
            {
                "sector_id": sector.id,
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "suggested_relation_type": sm.suggested_relation_type,
                "current_relation_type": sm.current_relation_type,
                "suggested_weight": sm.suggested_weight,
                "current_weight": sm.current_weight,
                "confidence": sm.confidence,
                "reason": sm.reason,
            }
            for sm, sector in rows
        ]

    async def _build_co_occurrence(
        self,
        cutoff_date: date,
    ) -> tuple[dict[str, dict[str, int]], str]:
        """构建板块共现矩阵（优先基于 CLS 看盘数据，缺失时回退到行情缓存）。

        Returns:
            (co_occurrence_map, source_type) 其中 source_type 为
            "cls_watch" 或 "market_cache"
        """
        from src.models.schema import CLSWatchData

        cutoff_ts = int(datetime.combine(cutoff_date, datetime.min.time()).timestamp())

        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData.sectors)
                .where(CLSWatchData.ctime >= cutoff_ts)
                .where(CLSWatchData.sectors.isnot(None))
            )
            rows = result.all()

        co_occurrence: dict[str, dict[str, int]] = {}

        for row in rows:
            try:
                sectors = json.loads(row.sectors) if row.sectors else []
                sectors = [s.strip() for s in sectors if isinstance(s, str) and s.strip()]
            except (json.JSONDecodeError, TypeError):
                continue

            for i, s1 in enumerate(sectors):
                for s2 in sectors[i + 1:]:
                    key1 = SectorIdentity.comparison_key(s1)
                    key2 = SectorIdentity.comparison_key(s2)
                    if key1 == key2:
                        continue
                    if key1 not in co_occurrence:
                        co_occurrence[key1] = {}
                    co_occurrence[key1][key2] = co_occurrence[key1].get(key2, 0) + 1
                    if key2 not in co_occurrence:
                        co_occurrence[key2] = {}
                    co_occurrence[key2][key1] = co_occurrence[key2].get(key1, 0) + 1

        if co_occurrence:
            return co_occurrence, "cls_watch"

        async with self.db.get_session() as session:
            result = await session.execute(
                select(MarketSector.trade_date, MarketSector.sector_name)
                .where(MarketSector.trade_date >= cutoff_date)
                .order_by(MarketSector.trade_date.asc())
            )
            market_rows = result.all()

        sectors_by_date: dict[date, list[str]] = {}
        for trade_date, sector_name in market_rows:
            if not sector_name:
                continue
            sectors_by_date.setdefault(trade_date, []).append(sector_name)

        for sectors in sectors_by_date.values():
            unique_keys = list({
                SectorIdentity.comparison_key(s.strip())
                for s in sectors
                if isinstance(s, str) and s.strip()
            })
            for i, key1 in enumerate(unique_keys):
                for key2 in unique_keys[i + 1:]:
                    if key1 == key2:
                        continue
                    if key1 not in co_occurrence:
                        co_occurrence[key1] = {}
                    co_occurrence[key1][key2] = co_occurrence[key1].get(key2, 0) + 1
                    if key2 not in co_occurrence:
                        co_occurrence[key2] = {}
                    co_occurrence[key2][key1] = co_occurrence[key2].get(key1, 0) + 1

        return co_occurrence, "market_cache"

    async def _suggest_for_existing_group(
        self,
        group: SectorGroup,
        eligible_sectors: list[TrackedSector],
        existing_members: list[SectorGroupMember],
        co_occurrence: dict[str, dict[str, int]],
        co_source: str,
        pending_suggestions: list[SectorGroupSuggestion],
        days: int,
    ) -> dict[str, int]:
        """为已有分组生成 add_members 建议。"""
        add_count = 0
        refreshed = 0

        # 获取该分组已有的成员 sector_id
        group_member_ids = {
            m.sector_id for m in existing_members if m.group_id == group.id
        }

        # 获取该分组已有的 pending 建议
        group_pending = [
            s for s in pending_suggestions
            if s.target_group_id == group.id and s.status == "pending"
        ]
        pending_sector_ids: set[int] = set()
        for s in group_pending:
            # 获取 pending 建议的成员
            async with self.db.get_session() as session:
                from sqlalchemy import select as sa_select
                result = await session.execute(
                    sa_select(SectorGroupSuggestionMember.sector_id).where(
                        SectorGroupSuggestionMember.suggestion_id == s.id
                    )
                )
                for row in result.all():
                    pending_sector_ids.add(row[0])

        # 检查共现关系
        group_key = SectorIdentity.comparison_key(group.canonical_name)
        related_sectors: list[tuple[TrackedSector, int]] = []

        # 从分组名/别名/关键词查找共现
        search_keys = [group_key]
        if group.aliases:
            try:
                for alias in json.loads(group.aliases):
                    search_keys.append(SectorIdentity.comparison_key(alias))
            except (json.JSONDecodeError, TypeError):
                pass
        if group.keywords:
            try:
                for kw in json.loads(group.keywords):
                    search_keys.append(SectorIdentity.comparison_key(kw))
            except (json.JSONDecodeError, TypeError):
                pass

        for sector in eligible_sectors:
            if sector.id in group_member_ids:
                continue
            if sector.status == "ignored":
                continue
            if sector.status == "inactive":
                continue

            sector_key = SectorIdentity.comparison_key(sector.canonical_name)

            # 检查共现
            max_co = 0
            for sk in search_keys:
                co = co_occurrence.get(sk, {}).get(sector_key, 0)
                max_co = max(max_co, co)

            if max_co >= 2:
                related_sectors.append((sector, max_co))

        if not related_sectors:
            return {"add_members": 0, "refreshed": 0}

        # 按共现次数排序
        related_sectors.sort(key=lambda x: -x[1])

        # 生成建议
        suggestion_members: list[dict[str, Any]] = []
        for sector, co_count in related_sectors[:10]:
            if sector.id in pending_sector_ids:
                refreshed += 1
                continue

            suggestion_members.append({
                "sector_id": sector.id,
                "relation_type": "related",
                "confidence": min(co_count / 10.0, 1.0),
                "reason": (
                    f"与分组 '{group.canonical_name}' 近{days}日"
                    f"{'行情缓存同日共现线索' if co_source == 'market_cache' else '共现'}{co_count}次"
                ),
            })

        if suggestion_members:
            async with self.db.get_session() as session:
                suggestion = SectorGroupSuggestion(
                    suggestion_type="add_members",
                    target_group_id=group.id,
                    status="pending",
                    confidence=max(m["confidence"] for m in suggestion_members),
                    reason=f"基于近{days}日共现分析，建议向分组 '{group.canonical_name}' 添加{len(suggestion_members)}个成员",
                )
                session.add(suggestion)
                await session.flush()
                await session.refresh(suggestion)

                for sm_data in suggestion_members:
                    member = SectorGroupSuggestionMember(
                        suggestion_id=suggestion.id,
                        sector_id=sm_data["sector_id"],
                        suggested_relation_type=sm_data["relation_type"],
                        confidence=sm_data["confidence"],
                        reason=sm_data["reason"],
                    )
                    session.add(member)

                add_count += 1

        return {"add_members": add_count, "refreshed": refreshed}

    async def _suggest_new_groups(
        self,
        eligible_sectors: list[TrackedSector],
        existing_groups: list[SectorGroup],
        existing_members: list[SectorGroupMember],
        co_occurrence: dict[str, dict[str, int]],
        co_source: str,
        pending_suggestions: list[SectorGroupSuggestion],
        days: int,
        ai_processor: Any = None,
    ) -> dict[str, int]:
        """检测新分组机会。

        四段流水线：
        1. 规则候选 - 从共现图构建聚类
        2. 主题约束 - 拆分/拒绝跨主题聚类
        3. AI 语义清洗 - 清洗候选成员
        4. 建议落库 - 持久化 pending 建议
        """
        # 获取已有 pending new_group 建议的名称
        pending_names = {
            SectorIdentity.comparison_key(s.suggested_group_name or "")
            for s in pending_suggestions
            if s.suggestion_type == "new_group" and s.status == "pending"
        }

        # 获取已在任何分组中的 sector_id
        all_member_ids = {m.sector_id for m in existing_members}

        # 阶段 1：构建候选聚类
        pair_count: dict[frozenset[str], int] = {}
        for key1, partners in co_occurrence.items():
            for key2, count in partners.items():
                if count >= 3:
                    pair = frozenset([key1, key2])
                    pair_count[pair] = pair_count.get(pair, 0) + count

        # 贪心聚类
        used_keys: set[str] = set()
        raw_clusters: list[set[str]] = []

        for pair, count in sorted(pair_count.items(), key=lambda x: -x[1]):
            keys = list(pair)
            cluster = set(keys)
            for k in keys:
                cluster.add(k)
                if k in co_occurrence:
                    for partner, c in co_occurrence[k].items():
                        if c >= 2 and partner not in used_keys:
                            cluster.add(partner)

            if len(cluster) >= 2:
                overlap = cluster & used_keys
                if not overlap:
                    used_keys.update(cluster)
                    raw_clusters.append(cluster)

        # market_cache 是弱信号，但同一内置主题内多个成员单日共现也应形成低置信线索。
        # 这能捕捉最新刚进榜的主题，例如“机器人概念 + 智能机器”。
        if co_source == "market_cache":
            sector_by_key = {
                SectorIdentity.comparison_key(s.canonical_name): s
                for s in eligible_sectors
            }
            theme_keys: dict[str, set[str]] = {}
            for key, sector in sector_by_key.items():
                theme = self.match_theme(sector.canonical_name)
                if theme is None:
                    continue
                if key not in co_occurrence:
                    continue
                has_same_theme_partner = False
                for partner, count in co_occurrence.get(key, {}).items():
                    partner_sector = sector_by_key.get(partner)
                    if not partner_sector:
                        continue
                    if count >= 1 and self.match_theme(partner_sector.canonical_name) == theme:
                        has_same_theme_partner = True
                        break
                if has_same_theme_partner:
                    theme_keys.setdefault(theme, set()).add(key)

            for keys in theme_keys.values():
                if len(keys) < 2:
                    continue
                if any(keys <= existing for existing in raw_clusters):
                    continue
                raw_clusters.append(keys)

        if not raw_clusters:
            return {"new_groups": 0}

        # 阶段 2：主题约束 - 为每个聚类匹配主题，拆分跨主题聚类
        candidate_clusters = await self._apply_theme_constraints(
            raw_clusters=raw_clusters,
            eligible_sectors=eligible_sectors,
            co_occurrence=co_occurrence,
            co_source=co_source,
        )
        candidate_clusters = self._deduplicate_candidate_clusters(candidate_clusters)

        # 阶段 3+4：AI 清洗 + 持久化
        new_count = 0
        for cluster in candidate_clusters[:10]:
            if len(cluster.members) < 2:
                continue

            # 检查是否已有匹配的分组
            matched_existing = False
            for group in existing_groups:
                group_key = SectorIdentity.comparison_key(group.canonical_name)
                for m in cluster.members:
                    if SectorIdentity.comparison_key(m.canonical_name) == group_key:
                        matched_existing = True
                        break
                if matched_existing:
                    break
            if matched_existing:
                continue

            # 确定建议名称，并先按建议名匹配已有分组。
            # 仅比较成员名会漏掉“机器人 + 智能机器 -> 人形机器人链”这类主题名命中。
            suggested_name = cluster.theme_name or cluster.members[0].canonical_name + "链"
            if self._find_existing_group_by_name(existing_groups, suggested_name):
                continue

            # AI 清洗
            cleaned = cluster
            if ai_processor:
                cleaned = await self._clean_cluster_with_ai(
                    cluster=cluster,
                    ai_processor=ai_processor,
                    existing_groups=existing_groups,
                    existing_members=existing_members,
                )

            if len(cleaned.members) < 2:
                continue

            # AI 可能改写建议名称，清洗后需要再次用最终名称匹配已有分组。
            suggested_name = cleaned.theme_name or suggested_name
            if self._find_existing_group_by_name(existing_groups, suggested_name):
                continue

            name_key = SectorIdentity.comparison_key(suggested_name)

            # 检查同名 pending 建议 - 刷新而非重复创建
            existing_pending = None
            for s in pending_suggestions:
                if (s.suggestion_type == "new_group"
                        and s.status == "pending"
                        and SectorIdentity.comparison_key(s.suggested_group_name or "") == name_key):
                    existing_pending = s
                    break

            # 确定置信度和原因
            confidence = self._calculate_cluster_confidence(cleaned)
            reason = self._build_cluster_reason(cleaned, days)

            # 构建 evidence
            evidence = self._build_cluster_evidence(cleaned, co_source, days)

            # 持久化
            if existing_pending:
                await self._refresh_pending_suggestion(
                    existing_pending=existing_pending,
                    suggested_name=suggested_name,
                    confidence=confidence,
                    reason=reason,
                    evidence=evidence,
                    members=cleaned.members,
                )
            else:
                await self._persist_new_group_suggestion(
                    suggested_name=suggested_name,
                    confidence=confidence,
                    reason=reason,
                    evidence=evidence,
                    members=cleaned.members,
                )

            new_count += 1

        return {"new_groups": new_count}

    @staticmethod
    def _deduplicate_candidate_clusters(
        clusters: list[CandidateCluster],
    ) -> list[CandidateCluster]:
        """同一主题只保留成员最多、共现最强的一条候选。"""
        best_by_theme: dict[str, CandidateCluster] = {}
        others: list[CandidateCluster] = []

        for cluster in clusters:
            if cluster.theme_name is None:
                others.append(cluster)
                continue

            current = best_by_theme.get(cluster.theme_name)
            if current is None:
                best_by_theme[cluster.theme_name] = cluster
                continue

            current_score = (
                len(current.members),
                sum(m.co_occurrence_count for m in current.members),
            )
            new_score = (
                len(cluster.members),
                sum(m.co_occurrence_count for m in cluster.members),
            )
            if new_score > current_score:
                best_by_theme[cluster.theme_name] = cluster

        deduped = list(best_by_theme.values()) + others
        deduped.sort(key=lambda c: (
            c.theme_name is None,
            -len(c.members),
            -sum(m.co_occurrence_count for m in c.members),
        ))
        return deduped

    @staticmethod
    def _find_existing_group_by_name(
        existing_groups: list[SectorGroup],
        name: str,
    ) -> SectorGroup | None:
        """按规范名、别名、关键词匹配已有分组。"""
        name_key = SectorIdentity.comparison_key(name)
        for group in existing_groups:
            if SectorIdentity.comparison_key(group.canonical_name) == name_key:
                return group

            for raw_values in (group.aliases, group.keywords):
                if not raw_values:
                    continue
                try:
                    values = json.loads(raw_values)
                except (json.JSONDecodeError, TypeError):
                    continue
                for value in values:
                    if SectorIdentity.comparison_key(str(value)) == name_key:
                        return group

        return None

    # ------------------------------------------------------------------
    # 主题约束与匹配
    # ------------------------------------------------------------------

    @staticmethod
    def match_theme(name: str) -> str | None:
        """匹配板块名称到内置主题（静态 fallback）。"""
        key = SectorIdentity.comparison_key(name)
        return _THEME_KEY_INDEX.get(key)

    async def match_theme_dynamic(self, name: str) -> str | None:
        """匹配板块名称到主题（优先使用动态注册表）。"""
        if self._theme_registry is not None:
            registry = await self._theme_registry.get_registry()
            return registry.match(name)
        return self.match_theme(name)

    async def _apply_theme_constraints(
        self,
        raw_clusters: list[set[str]],
        eligible_sectors: list[TrackedSector],
        co_occurrence: dict[str, dict[str, int]],
        co_source: str,
    ) -> list[CandidateCluster]:
        """对原始聚类应用主题约束，拆分跨主题聚类。"""
        # 建立 comparison_key → TrackedSector 映射
        sector_by_key: dict[str, TrackedSector] = {}
        for s in eligible_sectors:
            key = SectorIdentity.comparison_key(s.canonical_name)
            sector_by_key[key] = s

        result: list[CandidateCluster] = []

        for raw in raw_clusters:
            # 为每个 key 匹配主题
            key_themes: dict[str, str | None] = {}
            for k in raw:
                if k in sector_by_key:
                    key_themes[k] = await self.match_theme_dynamic(
                        sector_by_key[k].canonical_name
                    )
                else:
                    key_themes[k] = None

            # 按主题分组
            theme_groups: dict[str | None, list[str]] = {}
            for k, theme in key_themes.items():
                theme_groups.setdefault(theme, []).append(k)

            # 生成候选聚类
            for theme, keys in theme_groups.items():
                if len(keys) < 2:
                    continue

                members: list[CandidateMember] = []
                for k in keys:
                    sector = sector_by_key.get(k)
                    if not sector:
                        continue
                    # 获取共现计数
                    max_co = 0
                    for other_k in keys:
                        if other_k != k:
                            max_co = max(max_co, co_occurrence.get(k, {}).get(other_k, 0))

                    members.append(CandidateMember(
                        sector_id=sector.id,
                        canonical_name=sector.canonical_name,
                        sector_status=sector.status,
                        co_occurrence_count=max_co,
                        source=co_source,
                        theme_name=theme,
                    ))

                if len(members) < 2:
                    continue

                is_mixed = theme is None and len(theme_groups) > 1

                result.append(CandidateCluster(
                    members=tuple(members),
                    theme_name=theme,
                    source=co_source,
                    is_mixed_theme=is_mixed,
                ))

        # 排序：有主题的优先
        result.sort(key=lambda c: (c.theme_name is None, -len(c.members)))
        return result

    # ------------------------------------------------------------------
    # AI 语义清洗
    # ------------------------------------------------------------------

    async def _clean_cluster_with_ai(
        self,
        cluster: CandidateCluster,
        ai_processor: Any,
        existing_groups: list[SectorGroup],
        existing_members: list[SectorGroupMember],
    ) -> CandidateCluster:
        """使用 AI 对候选聚类做语义清洗。"""
        try:
            ai_result = await self._call_ai_cleaning(
                cluster=cluster,
                ai_processor=ai_processor,
                existing_groups=existing_groups,
                existing_members=existing_members,
            )
        except Exception as e:
            logger.warning("AI 清洗失败，回退到规则验证: %s", e)
            return self._rule_only_fallback(cluster)

        if not ai_result.accepted:
            logger.info("AI 拒绝聚类 '%s': %s", cluster.theme_name, ai_result.reason)
            return CandidateCluster(
                members=(),
                theme_name=cluster.theme_name,
                source=cluster.source,
                is_mixed_theme=cluster.is_mixed_theme,
            )

        # 验证 AI 输出
        candidate_ids = {m.sector_id for m in cluster.members}
        validated_members: list[CandidateMember] = []
        for ai_member in ai_result.accepted_members:
            sid = ai_member.get("sector_id")
            if sid not in candidate_ids:
                logger.warning("AI 返回未知 sector_id=%s，已忽略", sid)
                continue
            # 从原始成员查找信息
            for cm in cluster.members:
                if cm.sector_id == sid:
                    validated_members.append(CandidateMember(
                        sector_id=cm.sector_id,
                        canonical_name=cm.canonical_name,
                        sector_status=cm.sector_status,
                        co_occurrence_count=cm.co_occurrence_count,
                        source=cm.source,
                        theme_name=cm.theme_name,
                    ))
                    break

        # 最小成员数检查
        if len(validated_members) < 2:
            logger.info("AI 清洗后成员不足 2 个，丢弃")
            return CandidateCluster(
                members=(),
                theme_name=cluster.theme_name,
                source=cluster.source,
                is_mixed_theme=cluster.is_mixed_theme,
            )

        # 更新主题名（AI 可能提供更好的名称）
        theme_name = cluster.theme_name
        if ai_result.suggested_group_name:
            theme_name = ai_result.suggested_group_name

        return CandidateCluster(
            members=tuple(validated_members),
            theme_name=theme_name,
            source=cluster.source,
            is_mixed_theme=False,
        )

    async def _call_ai_cleaning(
        self,
        cluster: CandidateCluster,
        ai_processor: Any,
        existing_groups: list[SectorGroup],
        existing_members: list[SectorGroupMember],
    ) -> AICleaningResult:
        """调用 AI 进行结构化语义清洗。"""
        # 构建提示
        candidate_list = []
        for m in cluster.members:
            candidate_list.append({
                "sector_id": m.sector_id,
                "name": m.canonical_name,
                "status": m.sector_status,
                "co_occurrence_count": m.co_occurrence_count,
                "theme": m.theme_name,
            })

        existing_group_info = []
        for g in existing_groups:
            g_members = [
                m.sector_id for m in existing_members if m.group_id == g.id
            ]
            aliases = []
            if g.aliases:
                try:
                    aliases = json.loads(g.aliases)
                except (json.JSONDecodeError, TypeError):
                    pass
            keywords = []
            if g.keywords:
                try:
                    keywords = json.loads(g.keywords)
                except (json.JSONDecodeError, TypeError):
                    pass
            existing_group_info.append({
                "name": g.canonical_name,
                "aliases": aliases,
                "keywords": keywords,
                "member_count": len(g_members),
            })

        prompt = (
            "你是一个 A 股行业分析师。请判断以下候选板块是否属于同一产业链/主题。\n\n"
            "约束：\n"
            "- 只能保留输入列表中已有的 sector_id\n"
            "- 不能新增不存在的板块\n"
            "- 不能接受建议，只能清洗候选\n\n"
            f"候选分组主题: {cluster.theme_name or '未知'}\n"
            f"候选成员:\n{json.dumps(candidate_list, ensure_ascii=False, indent=2)}\n\n"
            f"已有分组:\n{json.dumps(existing_group_info, ensure_ascii=False, indent=2)}\n\n"
            "请严格按以下 JSON 格式返回（不要添加其他内容）：\n"
            "{\n"
            '  "accepted": true/false,\n'
            '  "suggested_group_name": "建议的分组名",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "reason": "判断理由",\n'
            '  "members": [{"sector_id": 1, "relation_type": "core/related", "confidence": 0.9, "reason": "原因"}],\n'
            '  "rejected_members": [{"sector_id": 9, "reason": "排除原因"}]\n'
            "}"
        )

        # 调用 AI
        response = await ai_processor._call_api(
            prompt=prompt,
            max_tokens=1000,
        )

        # 解析 JSON
        result = self._parse_ai_cleaning_response(response, cluster)
        return result

    @staticmethod
    def _parse_ai_cleaning_response(
        response: str,
        cluster: CandidateCluster,
    ) -> AICleaningResult:
        """解析 AI 清洗响应为结构化结果。"""
        # 尝试提取 JSON
        json_str = response.strip()
        # 处理 markdown 代码块
        if "```" in json_str:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]
        elif "{" in json_str:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]

        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return AICleaningResult(accepted=False, reason="AI 返回无效 JSON")

        # 验证基本字段
        accepted = data.get("accepted", False)
        confidence = data.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.0
        confidence = float(confidence)

        # 低置信度拒绝
        if confidence < 0.5:
            return AICleaningResult(
                accepted=False,
                confidence=confidence,
                reason=f"AI 置信度过低: {confidence}",
            )

        # 验证成员
        candidate_ids = {m.sector_id for m in cluster.members}
        accepted_members = []
        for m in data.get("members", []):
            sid = m.get("sector_id")
            if sid in candidate_ids:
                relation_type = m.get("relation_type", "related")
                if relation_type not in RELATION_TYPES:
                    relation_type = "related"
                accepted_members.append({
                    "sector_id": sid,
                    "relation_type": relation_type,
                    "confidence": float(m.get("confidence", 0.5)),
                    "reason": m.get("reason", ""),
                })

        rejected_members = []
        for m in data.get("rejected_members", []):
            sid = m.get("sector_id")
            if sid in candidate_ids:
                rejected_members.append({
                    "sector_id": sid,
                    "reason": m.get("reason", ""),
                })

        return AICleaningResult(
            accepted=accepted,
            suggested_group_name=data.get("suggested_group_name"),
            confidence=confidence,
            reason=data.get("reason"),
            accepted_members=accepted_members,
            rejected_members=rejected_members,
        )

    @staticmethod
    def _rule_only_fallback(cluster: CandidateCluster) -> CandidateCluster:
        """规则兜底：只保留有主题匹配的成员，无主题聚类直接丢弃。"""
        if cluster.theme_name is None:
            # 无主题匹配的 market-cache 聚类 → 丢弃
            return CandidateCluster(
                members=(),
                theme_name=None,
                source=cluster.source,
                is_mixed_theme=cluster.is_mixed_theme,
            )
        # 有主题匹配 → 保留所有成员
        return cluster

    # ------------------------------------------------------------------
    # 置信度与原因
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_cluster_confidence(cluster: CandidateCluster) -> float:
        """计算聚类置信度。"""
        if not cluster.members:
            return 0.0

        # 基础：平均共现计数
        avg_co = sum(m.co_occurrence_count for m in cluster.members) / len(cluster.members)
        base = min(avg_co / 10.0, 1.0)

        # 来源调整
        source_factor = 0.7 if cluster.source == "market_cache" else 1.0

        # 主题匹配加分
        theme_factor = 1.0 if cluster.theme_name else 0.5

        return round(min(base * source_factor * theme_factor, 1.0), 2)

    @staticmethod
    def _build_cluster_reason(cluster: CandidateCluster, days: int) -> str:
        """构建建议原因。"""
        member_count = len(cluster.members)
        names = ", ".join(m.canonical_name for m in cluster.members[:5])
        suffix = "等" if member_count > 5 else ""

        if cluster.source == "market_cache":
            return (
                f"近{days}日行情缓存同日共现线索发现{member_count}个板块关联"
                f"（{names}{suffix}），属于弱行情信号，非确认产业链关联"
            )

        return (
            f"近{days}日共现分析发现{member_count}个板块高频关联"
            f"（{names}{suffix}），建议创建新分组"
        )

    @staticmethod
    def _build_cluster_evidence(
        cluster: CandidateCluster,
        co_source: str,
        days: int,
    ) -> dict[str, Any]:
        """构建聚类 evidence。"""
        return {
            "source": co_source,
            "window_days": days,
            "theme_name": cluster.theme_name,
            "is_mixed_theme": cluster.is_mixed_theme,
            "members": [
                {
                    "sector_id": m.sector_id,
                    "name": m.canonical_name,
                    "co_occurrence_count": m.co_occurrence_count,
                    "theme_match": m.theme_name,
                }
                for m in cluster.members
            ],
            "ai_cleaned": False,
        }

    # ------------------------------------------------------------------
    # 建议持久化
    # ------------------------------------------------------------------

    async def _persist_new_group_suggestion(
        self,
        suggested_name: str,
        confidence: float,
        reason: str,
        evidence: dict[str, Any],
        members: tuple[CandidateMember, ...],
    ) -> None:
        """持久化新的 new_group 建议。"""
        async with self.db.get_session() as session:
            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name=suggested_name,
                status="pending",
                confidence=confidence,
                reason=reason,
                evidence_json=json.dumps(evidence, ensure_ascii=False),
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)

            for member in members[:10]:
                sm = SectorGroupSuggestionMember(
                    suggestion_id=suggestion.id,
                    sector_id=member.sector_id,
                    suggested_relation_type="related",
                    confidence=min(member.co_occurrence_count / 10.0, 1.0),
                    reason=f"共现聚类成员（来源: {member.source}）",
                )
                session.add(sm)

    async def _refresh_pending_suggestion(
        self,
        existing_pending: SectorGroupSuggestion,
        suggested_name: str,
        confidence: float,
        reason: str,
        evidence: dict[str, Any],
        members: tuple[CandidateMember, ...],
    ) -> None:
        """刷新已有的 pending 建议而非重复创建。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.id == existing_pending.id
                )
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return

            suggestion.confidence = confidence
            suggestion.reason = reason
            suggestion.evidence_json = json.dumps(evidence, ensure_ascii=False)
            if suggested_name:
                suggestion.suggested_group_name = suggested_name

            # 删除旧成员
            result = await session.execute(
                select(SectorGroupSuggestionMember).where(
                    SectorGroupSuggestionMember.suggestion_id == suggestion.id
                )
            )
            for old_member in result.scalars().all():
                await session.delete(old_member)

            # 添加新成员
            for member in members[:10]:
                sm = SectorGroupSuggestionMember(
                    suggestion_id=suggestion.id,
                    sector_id=member.sector_id,
                    suggested_relation_type="related",
                    confidence=min(member.co_occurrence_count / 10.0, 1.0),
                    reason=f"共现聚类成员（来源: {member.source}）",
                )
                session.add(sm)

    async def _collect_group_evidence(
        self,
        group_id: int,
        end_date: date,
        window_days: int,
    ) -> dict[str, Any]:
        """收集组级证据。"""
        async with self.db.get_session() as session:
            # 获取已确认成员
            result = await session.execute(
                select(SectorGroupMember, TrackedSector)
                .join(TrackedSector, SectorGroupMember.sector_id == TrackedSector.id)
                .where(SectorGroupMember.group_id == group_id)
            )
            members = result.all()

        evidence: dict[str, Any] = {
            "group_id": group_id,
            "end_date": end_date.isoformat(),
            "window_days": window_days,
            "member_summaries": [],
            "raw_evidence_count": 0,
        }

        for member, sector in members:
            # 对于历史回放：优先匹配目标日期，否则使用不晚于目标日期的最新报告。
            summary = await self._get_member_summary_for_date(sector.id, end_date)

            member_data: dict[str, Any] = {
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "relation_type": member.relation_type,
                "has_summary": summary is not None,
            }

            if summary:
                member_data["summary_date"] = summary.end_date.isoformat() if summary.end_date else None
                member_data["trend_status"] = summary.trend_status
                member_data["strength_level"] = summary.strength_level
                member_data["action_bias"] = summary.action_bias
                member_data["judgement"] = summary.judgement
                member_data["summary_content"] = summary.content
                if summary.evidence_json:
                    try:
                        member_data["evidence"] = json.loads(summary.evidence_json)
                    except (json.JSONDecodeError, TypeError):
                        member_data["evidence"] = {}

            evidence["member_summaries"].append(member_data)

        evidence["member_count"] = len(evidence["member_summaries"])

        return evidence

    def _build_member_evidence_quality(
        self,
        member_summaries: list[dict[str, Any]],
        group_prep_result: Any,
        target_date: date,
    ) -> list[dict[str, Any]]:
        """从成员报告证据与准备结果构建组级校验输入。"""
        prep_by_name = {
            r.sector_name: r
            for r in getattr(group_prep_result, "member_results", [])
        }

        quality: list[dict[str, Any]] = []
        for member in member_summaries:
            name = member.get("sector_name", "")
            evidence = member.get("evidence") or {}
            diagnostics = evidence.get("diagnostics", {})
            prep = prep_by_name.get(name)

            market_role = evidence.get("market_evidence_role") or (
                prep.market_role.value if prep is not None else "no_market"
            )
            confidence_tier = evidence.get("preparation_confidence") or (
                prep.confidence_tier.value if prep is not None else "low"
            )
            watch_count = int(diagnostics.get("cls_watch_count") or 0)
            telegraph_count = int(diagnostics.get("cls_telegraph_count") or 0)
            market_count = int(diagnostics.get("market_count") or 0)
            alias_market_count = int(diagnostics.get("alias_market_count") or 0)
            proxy_market_count = int(diagnostics.get("proxy_market_count") or 0)
            source_count = sum(
                1 for count in (
                    market_count + alias_market_count + proxy_market_count,
                    watch_count,
                    telegraph_count,
                )
                if count > 0
            )
            if source_count >= 2 and (watch_count + telegraph_count) >= 3:
                confidence_tier = "high"
            elif source_count >= 1 and (watch_count + telegraph_count) >= 3:
                confidence_tier = "medium"

            quality.append({
                "sector_name": name,
                "sector_status": member.get("sector_status", ""),
                "trend_status": member.get("trend_status", ""),
                "is_fresh": member.get("summary_date") == target_date.isoformat(),
                "confidence_tier": confidence_tier,
                "market_role": market_role,
                "has_multi_source": source_count >= 2,
                "watch_count": watch_count,
                "telegraph_count": telegraph_count,
                "market_count": market_count,
                "alias_market_count": alias_market_count,
                "proxy_market_count": proxy_market_count,
            })

        return quality

    async def _get_member_summary_for_date(
        self,
        sector_id: int,
        target_date: date,
    ) -> SectorTrendSummary | None:
        """获取成员在目标日期或之前的最新趋势报告。

        优先返回目标日期完全匹配的报告。
        如果无精确匹配，返回不晚于目标日期的最新报告。
        目标日期之后的报告不会被使用。
        """
        async with self.db.get_session() as session:
            # 优先精确匹配
            result = await session.execute(
                select(SectorTrendSummary)
                .where(SectorTrendSummary.sector_id == sector_id)
                .where(SectorTrendSummary.end_date == target_date)
            )
            summary = result.scalar_one_or_none()
            if summary:
                return summary

            # 回退到目标日期之前的最新报告
            result = await session.execute(
                select(SectorTrendSummary)
                .where(SectorTrendSummary.sector_id == sector_id)
                .where(SectorTrendSummary.end_date <= target_date)
                .order_by(SectorTrendSummary.end_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def _calculate_member_freshness(
        self,
        group_id: int,
        target_date: date,
        members: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """计算成员新鲜度。"""
        freshness = []
        for member in members:
            sector_id = member["sector_id"]
            sector_status = member.get("sector_status", "")

            # 历史回放只能使用目标日期及之前的报告，不能被未来报告误判为新鲜。
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(sql_func.max(SectorTrendSummary.end_date)).where(
                        SectorTrendSummary.sector_id == sector_id,
                        SectorTrendSummary.end_date <= target_date,
                    )
                )
                latest_usable_date = result.scalar()

            is_candidate = sector_status == "candidate"
            is_stale = False
            is_missing = False

            if not is_candidate:
                if latest_usable_date is None:
                    is_missing = True
                elif latest_usable_date < target_date:
                    is_stale = True

            freshness.append({
                "sector_name": member["sector_name"],
                "sector_status": sector_status,
                "relation_type": member.get("relation_type", "related"),
                "is_candidate": is_candidate,
                "is_stale": is_stale,
                "is_missing": is_missing,
                "latest_summary_date": latest_usable_date.isoformat() if latest_usable_date else None,
                "target_date": target_date.isoformat(),
            })

        return freshness

    async def _sector_has_report(
        self,
        sector_id: int,
        target_date: date,
    ) -> bool:
        """检查板块是否有目标日期的报告。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(sql_func.count(SectorTrendSummary.id)).where(
                    SectorTrendSummary.sector_id == sector_id,
                    SectorTrendSummary.end_date == target_date,
                )
            )
            return (result.scalar() or 0) > 0

    async def _get_latest_group_summary(
        self,
        group_id: int,
    ) -> SectorGroupTrendSummary | None:
        """获取分组最新趋势报告。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupTrendSummary)
                .where(SectorGroupTrendSummary.group_id == group_id)
                .order_by(SectorGroupTrendSummary.end_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def _save_group_trend_summary(
        self,
        group_id: int,
        group_name: str,
        end_date: date,
        window_days: int,
        content: str,
        trend_status: str | None = None,
        strength_level: str | None = None,
        action_bias: str | None = None,
        judgement: str | None = None,
        evidence_json: str | None = None,
        member_freshness_json: str | None = None,
    ) -> SectorGroupTrendSummary:
        """保存分组趋势报告（文件 + 数据库）。"""
        from src.services.sector_trend_service import sector_to_path_name

        path_name = sector_to_path_name(group_name)
        output_path = GROUP_OUTPUT_DIR / path_name / f"{end_date}.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("分组趋势报告已保存: %s", output_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupTrendSummary).where(
                    SectorGroupTrendSummary.group_id == group_id,
                    SectorGroupTrendSummary.end_date == end_date,
                )
            )
            summary = result.scalar_one_or_none()

            if summary:
                summary.content = content
                summary.trend_status = trend_status
                summary.strength_level = strength_level
                summary.action_bias = action_bias
                summary.judgement = judgement
                summary.evidence_json = evidence_json
                summary.member_freshness_json = member_freshness_json
                summary.output_path = str(output_path)
                summary.window_days = window_days
            else:
                summary = SectorGroupTrendSummary(
                    group_id=group_id,
                    group_name=group_name,
                    end_date=end_date,
                    window_days=window_days,
                    trend_status=trend_status,
                    strength_level=strength_level,
                    action_bias=action_bias,
                    judgement=judgement,
                    content=content,
                    evidence_json=evidence_json,
                    member_freshness_json=member_freshness_json,
                    output_path=str(output_path),
                )
                session.add(summary)

            await session.flush()
            await session.refresh(summary)

        return summary

    def _get_latest_trade_date(self) -> date:
        """获取最近交易日期。"""
        from src.services.market_analyzer import MarketAnalyzer
        analyzer = MarketAnalyzer(self.db)
        return analyzer.get_latest_trade_date()
