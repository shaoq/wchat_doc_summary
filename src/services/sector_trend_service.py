"""板块趋势跟踪服务 - 候选发现、证据收集、趋势更新、文件持久化。"""

import json
import logging
import re
import time as _time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    CLSTelegraph,
    CLSWatchData,
    MarketSector,
    SectorTrendSummary,
    TrackedSector,
)
from src.services import trade_calendar as _tc
from src.services.market_analyzer import MarketAnalyzer
from src.storage.database import Database

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output/sector_trends")

# 趋势状态标签枚举
TREND_STATUSES = (
    "主线加强", "主线延续", "分歧中继", "低位启动",
    "轮动补涨", "短线脉冲", "高位退潮", "暂无趋势",
)
STRENGTH_LEVELS = ("强", "中", "弱")
ACTION_BIASES = ("跟踪", "观察", "回避")


def sector_to_path_name(sector_name: str) -> str:
    """将板块名转换为路径安全字符串，保留展示名到输出路径的映射。

    策略: 保留中文字符（它们在大多数现代文件系统上安全），仅替换
    文件系统保留字符。对于纯特殊字符名称，回退到 URL 编码。

    Args:
        sector_name: 板块显示名

    Returns:
        路径安全字符串
    """
    # 替换文件系统不安全字符
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    result = re.sub(unsafe_chars, "_", sector_name.strip())
    # 去除首尾空格和点号
    result = result.strip(". ")
    # 空结果回退
    if not result:
        result = unicodedata.normalize("NFKD", sector_name)
        result = re.sub(r"[^\w]", "_", result)
    # 截断过长名称
    if len(result) > 64:
        result = result[:64]
    return result or "unknown"


class SectorIdentity:
    """板块名称归一化与去重工具。"""

    # 常见板块名称后缀，归一化时去除
    SUFFIXES_TO_CLEAN = (
        "板块", "概念", "行业", "题材", "指数",
    )

    @staticmethod
    def normalize(name: str) -> str:
        """归一化板块名称，生成规范名和稳定比较键。

        Args:
            name: 原始板块名称

        Returns:
            规范化后的名称
        """
        result = name.strip()
        # 去除前后空白
        result = re.sub(r"\s+", "", result)
        # 去除常见后缀以获得更稳定的比较键
        for suffix in SectorIdentity.SUFFIXES_TO_CLEAN:
            if result.endswith(suffix) and len(result) > len(suffix):
                result = result[: -len(suffix)]
                break
        return result

    @staticmethod
    def comparison_key(name: str) -> str:
        """生成稳定的比较键，用于归一化名称匹配。

        Args:
            name: 板块名称

        Returns:
            小写、去空白、去后缀的比较键
        """
        return SectorIdentity.normalize(name).lower()

    @staticmethod
    def deduplicate(
        candidates: list[dict[str, Any]],
        existing: list[TrackedSector],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """对候选板块进行保守去重。

        高置信合并规则：
        1. 稳定代码相同
        2. 规范名完全相同
        3. 命中已有显式别名

        不自动合并的保留为独立候选。

        Args:
            candidates: 新发现的候选列表，每项含 name/code 等字段
            existing: 已存在的 TrackedSector 列表

        Returns:
            (merged_candidates, new_candidates)
            merged_candidates: 合并到已有板块的候选
            new_candidates: 未匹配到已有板块的新候选
        """
        # 构建已有板块的查找索引
        code_index: dict[str, TrackedSector] = {}
        name_index: dict[str, TrackedSector] = {}
        alias_index: dict[str, TrackedSector] = {}

        for sector in existing:
            if sector.sector_code:
                code_index[sector.sector_code] = sector
            name_key = SectorIdentity.comparison_key(sector.canonical_name)
            name_index[name_key] = sector
            if sector.aliases:
                try:
                    aliases = json.loads(sector.aliases)
                    for alias in aliases:
                        alias_key = SectorIdentity.comparison_key(alias)
                        alias_index[alias_key] = sector
                except (json.JSONDecodeError, TypeError):
                    pass

        merged: list[dict[str, Any]] = []
        new: list[dict[str, Any]] = []

        for candidate in candidates:
            code = candidate.get("code")
            name = candidate.get("name", "")

            # 规则 1: 稳定代码匹配
            if code and code in code_index:
                candidate["matched_sector_id"] = code_index[code].id
                merged.append(candidate)
                continue

            # 规则 2: 规范名匹配
            name_key = SectorIdentity.comparison_key(name)
            if name_key in name_index:
                candidate["matched_sector_id"] = name_index[name_key].id
                merged.append(candidate)
                continue

            # 规则 3: 别名匹配
            if name_key in alias_index:
                candidate["matched_sector_id"] = alias_index[name_key].id
                merged.append(candidate)
                continue

            new.append(candidate)

        return merged, new

    @staticmethod
    def find_possible_matches(
        name: str,
        existing: list[TrackedSector],
    ) -> list[TrackedSector]:
        """查找语义或文本相似的板块，用于提示用户但不自动合并。

        简单策略: 检查名称是否包含或被包含于已有板块名称。

        Args:
            name: 待检查的板块名称
            existing: 已有板块列表

        Returns:
            可能相关的板块列表
        """
        norm = SectorIdentity.normalize(name)
        possible: list[TrackedSector] = []

        for sector in existing:
            sector_norm = SectorIdentity.normalize(sector.canonical_name)
            # 跳过自身
            if norm == sector_norm:
                continue
            # 包含关系检查（双向）
            if norm in sector_norm or sector_norm in norm:
                possible.append(sector)

        return possible


class SectorTrendAnalyzer:
    """板块趋势分析服务。

    负责候选发现、证据收集、单板块更新、批量更新、文件持久化。
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self._market_analyzer = MarketAnalyzer(db)

    # ------------------------------------------------------------------
    # 候选发现
    # ------------------------------------------------------------------

    async def discover_sectors(self, days: int = 10) -> dict[str, Any]:
        """从多个来源发现候选板块。

        来源:
        1. 缓存的 MarketSector 行情强弱榜
        2. CLS 看盘数据中的板块标签

        Args:
            days: 回看天数

        Returns:
            发现结果统计
        """
        cutoff_date = date.today() - timedelta(days=days)
        candidates: list[dict[str, Any]] = []

        # 来源 1: MarketSector 缓存
        cache_candidates = await self._discover_from_market_cache(cutoff_date)
        candidates.extend(cache_candidates)

        # 来源 2: CLS 看盘板块标签
        cls_candidates = await self._discover_from_cls_watch(cutoff_date)
        candidates.extend(cls_candidates)

        # 去重候选自身（同名称合并）
        seen_names: dict[str, dict[str, Any]] = {}
        for c in candidates:
            key = SectorIdentity.comparison_key(c["name"])
            if key not in seen_names:
                seen_names[key] = c
            else:
                # 合并来源信息
                existing = seen_names[key]
                if c.get("code") and not existing.get("code"):
                    existing["code"] = c["code"]
                if c.get("source") and existing.get("source") != c.get("source"):
                    sources = {existing.get("source", ""), c.get("source", "")}
                    existing["source"] = "+".join(s for s in sources if s)

        unique_candidates = list(seen_names.values())

        # 与已有板块去重
        existing_sectors = await self._list_all_sectors()
        merged, new_candidates = SectorIdentity.deduplicate(
            unique_candidates, existing_sectors,
        )

        # 更新已有板块的发现元数据
        await self._update_discovery_metadata(merged)

        # 创建新候选
        created_count = 0
        for candidate in new_candidates:
            await self._create_candidate(candidate)
            created_count += 1

        return {
            "total_discovered": len(unique_candidates),
            "merged_into_existing": len(merged),
            "new_candidates": created_count,
        }

    async def _discover_from_market_cache(
        self, cutoff_date: date,
    ) -> list[dict[str, Any]]:
        """从缓存的 MarketSector 表发现候选。"""
        candidates: list[dict[str, Any]] = []

        async with self.db.get_session() as session:
            result = await session.execute(
                select(
                    MarketSector.sector_name,
                    MarketSector.sector_code,
                    sql_func.max(MarketSector.trade_date).label("last_seen"),
                    sql_func.count(MarketSector.id).label("appearances"),
                )
                .where(MarketSector.trade_date >= cutoff_date)
                .group_by(MarketSector.sector_code)
                .order_by(sql_func.count(MarketSector.id).desc())
                .limit(100)
            )
            rows = result.all()

        for row in rows:
            candidates.append({
                "name": row.sector_name,
                "code": row.sector_code,
                "source": "market_cache",
                "last_seen_date": row.last_seen,
                "appearances": row.appearances,
                "discovery_reason": f"近{len(rows)}日行情强弱榜出现{row.appearances}次",
            })

        return candidates

    async def _discover_from_cls_watch(
        self, cutoff_date: date,
    ) -> list[dict[str, Any]]:
        """从 CLS 看盘数据发现候选。"""
        candidates: list[dict[str, Any]] = []
        cutoff_ts = int(datetime.combine(cutoff_date, datetime.min.time()).timestamp())

        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData.sectors)
                .where(CLSWatchData.ctime >= cutoff_ts)
                .where(CLSWatchData.sectors.isnot(None))
            )
            rows = result.all()

        sector_counts: dict[str, int] = {}
        for row in rows:
            try:
                sectors = json.loads(row.sectors) if row.sectors else []
                for s in sectors:
                    if s and isinstance(s, str):
                        sector_counts[s] = sector_counts.get(s, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        for name, count in sorted(sector_counts.items(), key=lambda x: -x[1])[:50]:
            candidates.append({
                "name": name,
                "code": None,
                "source": "cls_watch",
                "discovery_reason": f"看盘数据提及{count}次",
            })

        return candidates

    async def _update_discovery_metadata(
        self, merged: list[dict[str, Any]],
    ) -> None:
        """更新已匹配板块的发现元数据。"""
        async with self.db.get_session() as session:
            for item in merged:
                sector_id = item.get("matched_sector_id")
                if not sector_id:
                    continue

                result = await session.execute(
                    select(TrackedSector).where(TrackedSector.id == sector_id)
                )
                sector = result.scalar_one_or_none()
                if not sector:
                    continue

                last_seen = item.get("last_seen_date")
                if isinstance(last_seen, date):
                    if sector.last_seen_date is None or last_seen > sector.last_seen_date:
                        sector.last_seen_date = last_seen

                # 合并源代码
                new_code = item.get("code")
                if new_code:
                    existing_codes = set()
                    if sector.source_codes:
                        try:
                            existing_codes = set(json.loads(sector.source_codes))
                        except (json.JSONDecodeError, TypeError):
                            pass
                    existing_codes.add(new_code)
                    sector.source_codes = json.dumps(sorted(existing_codes), ensure_ascii=False)

    async def _create_candidate(self, candidate: dict[str, Any]) -> None:
        """创建新的候选板块记录。"""
        name = candidate["name"]
        canonical_name = SectorIdentity.normalize(name)

        # 去重检查: 规范名不能重复
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.canonical_name == canonical_name
                )
            )
            if result.scalar_one_or_none():
                return

            sector = TrackedSector(
                canonical_name=canonical_name,
                sector_code=candidate.get("code"),
                status="candidate",
                source=candidate.get("source", "unknown"),
                first_seen_date=candidate.get("last_seen_date", date.today()),
                last_seen_date=candidate.get("last_seen_date", date.today()),
                discovery_reason=candidate.get("discovery_reason", ""),
            )
            session.add(sector)

    # ------------------------------------------------------------------
    # 列表与查询
    # ------------------------------------------------------------------

    async def _list_all_sectors(self) -> list[TrackedSector]:
        """获取所有板块记录。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).order_by(
                    TrackedSector.last_seen_date.desc().nullslast()
                )
            )
            return list(result.scalars().all())

    async def list_sectors(
        self,
        status: str | None = None,
        source: str | None = None,
        active_days: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """列出板块，支持筛选。

        Args:
            status: 状态筛选
            source: 来源筛选
            active_days: 活跃窗口天数
            limit: 返回数量

        Returns:
            板块信息列表
        """
        async with self.db.get_session() as session:
            query = select(TrackedSector)

            if status:
                query = query.where(TrackedSector.status == status)
            else:
                # 默认显示 tracked 和 candidate
                query = query.where(
                    TrackedSector.status.in_(["tracked", "candidate"])
                )

            if source:
                query = query.where(TrackedSector.source == source)

            if active_days:
                cutoff = date.today() - timedelta(days=active_days)
                query = query.where(TrackedSector.last_seen_date >= cutoff)

            query = query.order_by(
                TrackedSector.last_seen_date.desc().nullslast()
            ).limit(limit)

            result = await session.execute(query)
            sectors = result.scalars().all()

        return [
            {
                "id": s.id,
                "canonical_name": s.canonical_name,
                "sector_code": s.sector_code,
                "status": s.status,
                "source": s.source,
                "last_seen_date": s.last_seen_date.isoformat() if s.last_seen_date else None,
                "last_updated_date": s.last_updated_date.isoformat() if s.last_updated_date else None,
                "discovery_reason": s.discovery_reason,
            }
            for s in sectors
        ]

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    async def init_sector(self, sector_name: str) -> dict[str, Any]:
        """初始化板块为跟踪状态。

        如果已有候选板块则提升为 tracked，否则创建新的 tracked 板块。

        Args:
            sector_name: 板块名称

        Returns:
            操作结果
        """
        canonical = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            # 查找已有记录
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.canonical_name == canonical
                )
            )
            sector = result.scalar_one_or_none()

            if sector:
                if sector.status == "tracked":
                    return {
                        "action": "already_tracked",
                        "sector_id": sector.id,
                        "canonical_name": sector.canonical_name,
                    }
                # 提升为 tracked
                sector.status = "tracked"
                return {
                    "action": "promoted",
                    "sector_id": sector.id,
                    "canonical_name": sector.canonical_name,
                    "previous_status": sector.status,
                }

            # 创建新的 tracked 板块
            sector = TrackedSector(
                canonical_name=canonical,
                status="tracked",
                source="manual",
                first_seen_date=date.today(),
                last_seen_date=date.today(),
                discovery_reason="手动初始化",
            )
            session.add(sector)
            await session.flush()

            return {
                "action": "created",
                "sector_id": sector.id,
                "canonical_name": sector.canonical_name,
            }

    async def _ensure_tracked(self, sector_name: str) -> TrackedSector:
        """确保板块处于 tracked 状态，用于 update 自动初始化。"""
        canonical = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.canonical_name == canonical
                )
            )
            sector = result.scalar_one_or_none()

            if sector:
                if sector.status != "tracked":
                    sector.status = "tracked"
                await session.flush()
                await session.refresh(sector)
                return sector

            sector = TrackedSector(
                canonical_name=canonical,
                status="tracked",
                source="auto_init",
                first_seen_date=date.today(),
                last_seen_date=date.today(),
                discovery_reason="update 自动初始化",
            )
            session.add(sector)
            await session.flush()
            await session.refresh(sector)
            return sector

    # ------------------------------------------------------------------
    # 证据收集
    # ------------------------------------------------------------------

    async def collect_sector_evidence(
        self,
        sector_name: str,
        end_date: date,
        window_days: int = 10,
    ) -> dict[str, Any]:
        """收集单个板块的证据数据。

        来源:
        1. MarketSector 缓存中的近期表现
        2. CLS 看盘数据中的相关标签
        3. CLS 电报中的相关提及

        Args:
            sector_name: 板块名称
            end_date: 结束日期
            window_days: 回看窗口天数

        Returns:
            证据数据字典
        """
        start_date = end_date - timedelta(days=window_days)
        evidence: dict[str, Any] = {
            "sector_name": sector_name,
            "end_date": end_date.isoformat(),
            "window_days": window_days,
            "is_sparse": True,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
        }

        total_evidence = 0

        # 1. MarketSector 缓存
        async with self.db.get_session() as session:
            canonical = SectorIdentity.normalize(sector_name)
            result = await session.execute(
                select(MarketSector)
                .where(MarketSector.trade_date >= start_date)
                .where(MarketSector.trade_date <= end_date)
                .where(
                    (MarketSector.sector_code == None)  # noqa: E711
                    | (MarketSector.sector_name.contains(canonical[:2]))
                )
                .order_by(MarketSector.trade_date.desc())
            )
            sectors = result.scalars().all()

        # 精确过滤名称匹配
        matched_sectors = [
            s for s in sectors
            if SectorIdentity.comparison_key(s.sector_name) == SectorIdentity.comparison_key(sector_name)
        ]

        if matched_sectors:
            evidence["market_appearances"] = [
                {
                    "trade_date": s.trade_date.isoformat() if s.trade_date else None,
                    "sector_name": s.sector_name,
                    "change_pct": s.change_pct,
                    "amount": s.amount,
                    "main_inflow": s.main_inflow,
                }
                for s in matched_sectors
            ]
            total_evidence += len(matched_sectors)

        # 2. CLS 看盘数据
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(
            datetime.combine(end_date, datetime.max.time()).timestamp()
        )
        canonical_key = SectorIdentity.comparison_key(sector_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData)
                .where(CLSWatchData.ctime >= start_ts)
                .where(CLSWatchData.ctime <= end_ts)
                .where(CLSWatchData.sectors.isnot(None))
            )
            watch_items = result.scalars().all()

        watch_mentions = []
        for item in watch_items:
            try:
                item_sectors = json.loads(item.sectors) if item.sectors else []
                if any(
                    canonical_key in SectorIdentity.comparison_key(s)
                    for s in item_sectors
                    if isinstance(s, str)
                ):
                    watch_mentions.append({
                        "title": item.title,
                        "content": (item.content or "")[:200],
                        "publish_time": datetime.fromtimestamp(item.ctime).strftime("%Y-%m-%d %H:%M") if item.ctime else None,
                        "sectors": item_sectors,
                        "stocks": json.loads(item.stocks) if item.stocks else [],
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        if watch_mentions:
            evidence["cls_watch_mentions"] = watch_mentions
            total_evidence += len(watch_mentions)

        # 3. CLS 电报提及
        telegraph_mentions = await self._collect_telegraph_mentions(
            sector_name, start_date, end_date,
        )
        if telegraph_mentions:
            evidence["cls_telegraph_mentions"] = telegraph_mentions
            total_evidence += len(telegraph_mentions)

        # 4. 稀疏证据判断与缺口元数据
        evidence["is_sparse"] = total_evidence < 3
        evidence["total_evidence_count"] = total_evidence

        # 显式缺口标记（用于历史回填场景）
        gaps: list[str] = []
        if not matched_sectors:
            gaps.append("market_sector_cache_missing")
        if not watch_mentions:
            gaps.append("cls_watch_missing")
        if not telegraph_mentions:
            gaps.append("cls_telegraph_missing")
        evidence["data_gaps"] = gaps

        # 5. 诊断计数（用于历史回放、矩阵视图和调试）
        evidence["diagnostics"] = {
            "market_count": len(matched_sectors),
            "cls_watch_count": len(watch_mentions),
            "cls_telegraph_count": len(telegraph_mentions),
            "total_evidence_count": total_evidence,
            "data_gap_count": len(gaps),
        }

        return evidence

    async def _collect_telegraph_mentions(
        self,
        sector_name: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """从存储的 CLS 电报中收集匹配板块名称的提及。"""
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())
        canonical_key = SectorIdentity.comparison_key(sector_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSTelegraph)
                .where(CLSTelegraph.ctime >= start_ts)
                .where(CLSTelegraph.ctime <= end_ts)
                .where(
                    (CLSTelegraph.title.contains(sector_name))
                    | (CLSTelegraph.content.contains(sector_name))
                )
                .order_by(CLSTelegraph.ctime.desc())
            )
            telegraphs = result.scalars().all()

        mentions: list[dict[str, Any]] = []
        for tg in telegraphs:
            mentions.append({
                "title": tg.title,
                "content": (tg.content or "")[:200],
                "publish_time": datetime.fromtimestamp(tg.ctime).strftime("%Y-%m-%d %H:%M") if tg.ctime else None,
                "level": tg.level,
                "category": tg.category,
            })

        return mentions

    # ------------------------------------------------------------------
    # 趋势更新
    # ------------------------------------------------------------------

    async def get_previous_summary(
        self,
        sector_id: int,
        *,
        before_date: date | None = None,
    ) -> SectorTrendSummary | None:
        """获取板块最近一次趋势总结。

        Args:
            sector_id: 板块 ID
            before_date: 如果指定，只返回 end_date < before_date 的总结，
                         用于日期回放时避免使用未来报告作为先前上下文。
        """
        async with self.db.get_session() as session:
            stmt = (
                select(SectorTrendSummary)
                .where(SectorTrendSummary.sector_id == sector_id)
            )
            if before_date is not None:
                stmt = stmt.where(SectorTrendSummary.end_date < before_date)
            stmt = stmt.order_by(SectorTrendSummary.end_date.desc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_trend_summary(
        self,
        sector: TrackedSector,
        end_date: date,
        window_days: int,
        content: str,
        trend_status: str | None = None,
        strength_level: str | None = None,
        action_bias: str | None = None,
        judgement: str | None = None,
        evidence_json: str | None = None,
    ) -> SectorTrendSummary:
        """保存板块趋势总结（文件 + 数据库）。

        Args:
            sector: 板块记录
            end_date: 结束日期
            window_days: 回看窗口
            content: 报告内容
            trend_status: 趋势状态
            strength_level: 强度等级
            action_bias: 操作倾向
            judgement: 研判摘要
            evidence_json: 证据 JSON

        Returns:
            保存的 SectorTrendSummary
        """
        # 生成输出路径
        path_name = sector_to_path_name(sector.canonical_name)
        output_path = OUTPUT_DIR / path_name / f"{end_date}.md"

        # 保存文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("板块趋势报告已保存: %s", output_path)

        # 保存到数据库 (upsert)
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorTrendSummary).where(
                    SectorTrendSummary.sector_id == sector.id,
                    SectorTrendSummary.end_date == end_date,
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
                summary.output_path = str(output_path)
                summary.window_days = window_days
            else:
                summary = SectorTrendSummary(
                    sector_id=sector.id,
                    sector_name=sector.canonical_name,
                    sector_code=sector.sector_code,
                    end_date=end_date,
                    window_days=window_days,
                    trend_status=trend_status,
                    strength_level=strength_level,
                    action_bias=action_bias,
                    judgement=judgement,
                    content=content,
                    evidence_json=evidence_json,
                    output_path=str(output_path),
                )
                session.add(summary)

            await session.flush()
            await session.refresh(summary)

        # 更新板块的最后更新日期
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.id == sector.id)
            )
            db_sector = result.scalar_one_or_none()
            if db_sector:
                db_sector.last_updated_date = end_date

        return summary

    async def update_sector_trend(
        self,
        sector_name: str,
        days: int = 10,
        *,
        ai_processor: Any = None,
        force: bool = False,
        progress_callback: Callable[[str, str], None] | None = None,
        report_date: date | None = None,
        skip_repair: bool = False,
    ) -> dict[str, Any]:
        """更新单个板块趋势。

        完整流程:
        1. 确保板块为 tracked 状态
        2. 检查是否已有当日更新（除非 force）
        3. 修复 CLS 看盘板块归属（除非 skip_repair）
        4. 收集证据
        5. 获取上次总结
        6. 生成新总结
        7. 保存

        Args:
            sector_name: 板块名称
            days: 回看窗口天数
            ai_processor: AI 处理器实例
            force: 是否强制重新生成
            progress_callback: 进度回调 (stage_name, detail)
            report_date: 报告日期（默认最近交易日）
            skip_repair: 是否跳过 CLS 看盘板块归属修复

        Returns:
            更新结果
        """
        from src.services.trade_calendar import get_previous_trade_date, is_trade_day

        def _emit(stage: str, detail: str = "") -> None:
            if progress_callback is not None:
                progress_callback(stage, detail)

        # 1. 确保板块为 tracked
        sector = await self._ensure_tracked(sector_name)

        # 2. 确定结束日期（report_date 或最近交易日）
        end_date = report_date or self._market_analyzer.get_latest_trade_date()

        # 3. 检查是否已有更新
        if not force:
            existing = await self.get_previous_summary(sector.id)
            if existing and existing.end_date == end_date:
                _emit("skipped", "今日已更新")
                return {
                    "action": "skipped",
                    "sector_name": sector.canonical_name,
                    "reason": "今日已更新，使用 --force 重新生成",
                }

        # 4. 修复 CLS 看盘板块归属（日期回放时，只使用本地已有数据）
        repair_result = None
        if not skip_repair:
            _emit("repair", "修复 CLS 看盘板块归属...")
            try:
                from src.services.cls_watch_repair import ClsWatchRepairService
                repair_service = ClsWatchRepairService(self.db)
                repair_result = await repair_service.repair_window(end_date, days)
            except Exception as e:
                logger.warning("CLS 看盘板块归属修复失败，继续使用已有数据: %s", e)

        # 5. 收集证据
        _emit("evidence", "收集板块证据...")
        evidence = await self.collect_sector_evidence(
            sector.canonical_name, end_date, days,
        )

        # 6. 获取上次总结（日期回放时只使用目标日期之前的报告）
        previous_summary = await self.get_previous_summary(
            sector.id, before_date=end_date,
        )
        previous_context = None
        if previous_summary:
            previous_context = {
                "trend_status": previous_summary.trend_status,
                "strength_level": previous_summary.strength_level,
                "action_bias": previous_summary.action_bias,
                "judgement": previous_summary.judgement,
                "content": previous_summary.content,
                "end_date": previous_summary.end_date.isoformat() if previous_summary.end_date else None,
            }

        # 7. AI 生成
        if ai_processor is None:
            return {
                "action": "no_ai_processor",
                "sector_name": sector.canonical_name,
                "evidence": evidence,
                "repair_result": repair_result,
            }

        _emit("ai", "AI 生成板块趋势...")
        content, labels = await ai_processor.generate_sector_trend_summary(
            sector_name=sector.canonical_name,
            evidence=evidence,
            previous_summary=previous_context,
            end_date=end_date.isoformat(),
            window_days=days,
        )

        # 8. 保存（包含修复诊断信息）
        _emit("save", "保存板块报告...")

        # 将修复诊断信息嵌入证据中
        if repair_result:
            evidence["repair_diagnostics"] = {
                "repaired": repair_result.repaired,
                "unchanged": repair_result.unchanged,
                "unmatched": repair_result.unmatched,
                "low_confidence": repair_result.low_confidence,
            }

        summary = await self.save_trend_summary(
            sector=sector,
            end_date=end_date,
            window_days=days,
            content=content,
            trend_status=labels.get("trend_status"),
            strength_level=labels.get("strength_level"),
            action_bias=labels.get("action_bias"),
            judgement=labels.get("judgement"),
            evidence_json=json.dumps(evidence, ensure_ascii=False),
        )

        result = {
            "action": "updated",
            "sector_name": sector.canonical_name,
            "end_date": end_date.isoformat(),
            "output_path": summary.output_path,
            "trend_status": labels.get("trend_status"),
            "strength_level": labels.get("strength_level"),
            "action_bias": labels.get("action_bias"),
        }
        if repair_result:
            result["repair_result"] = repair_result
        return result

    # ------------------------------------------------------------------
    # 批量更新
    # ------------------------------------------------------------------

    async def update_all_sector_trends(
        self,
        *,
        limit: int | None = None,
        force: bool = False,
        continue_on_error: bool = True,
        ai_processor: Any = None,
        days: int = 10,
        report_date: date | None = None,
        skip_repair: bool = False,
    ) -> dict[str, Any]:
        """批量更新所有 tracked 板块趋势。

        Args:
            limit: 最大更新数量
            force: 是否强制重新生成
            continue_on_error: 是否在错误时继续
            ai_processor: AI 处理器实例
            days: 回看窗口天数
            report_date: 报告日期（默认最近交易日）
            skip_repair: 是否跳过 CLS 看盘板块归属修复

        Returns:
            批量更新结果
        """
        async with self.db.get_session() as session:
            query = select(TrackedSector).where(
                TrackedSector.status == "tracked"
            ).order_by(
                TrackedSector.last_updated_date.asc().nullsfirst()
            )
            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            sectors = list(result.scalars().all())

        # 批量修复：对整个证据窗口运行一次修复，避免每个板块重复修复
        repair_result = None
        if not skip_repair:
            end_date = report_date or self._market_analyzer.get_latest_trade_date()
            try:
                from src.services.cls_watch_repair import ClsWatchRepairService
                repair_service = ClsWatchRepairService(self.db)
                repair_result = await repair_service.repair_window(end_date, days)
            except Exception as e:
                logger.warning("批量 CLS 看盘板块归属修复失败，继续使用已有数据: %s", e)

        results: list[dict[str, Any]] = []
        success_count = 0
        skipped_count = 0
        failed_count = 0

        for sector in sectors:
            try:
                update_result = await self.update_sector_trend(
                    sector.canonical_name,
                    days=days,
                    ai_processor=ai_processor,
                    force=force,
                    report_date=report_date,
                    skip_repair=True,  # 批量模式已在上面统一修复
                )
                results.append(update_result)
                if update_result.get("action") == "updated":
                    success_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error("更新板块 %s 失败: %s", sector.canonical_name, e)
                failed_count += 1
                results.append({
                    "action": "failed",
                    "sector_name": sector.canonical_name,
                    "error": str(e),
                })
                if not continue_on_error:
                    break

        batch_result = {
            "total": len(sectors),
            "success": success_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "results": results,
        }
        if repair_result:
            batch_result["repair_result"] = repair_result
        return batch_result

    # ------------------------------------------------------------------
    # 查看与历史
    # ------------------------------------------------------------------

    async def show_latest(self, sector_name: str) -> dict[str, Any] | None:
        """查看板块最新趋势总结。"""
        canonical = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.canonical_name == canonical
                )
            )
            sector = result.scalar_one_or_none()
            if not sector:
                return None

            summary = await self.get_previous_summary(sector.id)
            if not summary:
                return {
                    "sector_name": sector.canonical_name,
                    "status": sector.status,
                    "has_summary": False,
                }

            return {
                "sector_name": sector.canonical_name,
                "status": sector.status,
                "has_summary": True,
                "end_date": summary.end_date.isoformat() if summary.end_date else None,
                "trend_status": summary.trend_status,
                "strength_level": summary.strength_level,
                "action_bias": summary.action_bias,
                "content": summary.content,
                "output_path": summary.output_path,
            }

    async def history(
        self, sector_name: str, limit: int = 20,
    ) -> list[dict[str, Any]]:
        """查看板块趋势更新历史。"""
        canonical = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.canonical_name == canonical
                )
            )
            sector = result.scalar_one_or_none()
            if not sector:
                return []

            result = await session.execute(
                select(SectorTrendSummary)
                .where(SectorTrendSummary.sector_id == sector.id)
                .order_by(SectorTrendSummary.end_date.desc())
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
