"""CLS 看盘数据板块归属修复服务 - 从本地证据回填空 sectors 字段。"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import CLSWatchData, TrackedSector
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import Database

logger = logging.getLogger(__name__)

# 置信度等级
CONFIDENCE_HIGH = "high"  # exact name / alias / code match
CONFIDENCE_MEDIUM = "medium"  # theme dictionary / learned term match
CONFIDENCE_LOW = "low"  # keyword / stock-based match


@dataclass(frozen=True)
class AttributionMatch:
    """单条归属匹配结果。"""

    sector_name: str
    confidence: str  # high / medium / low
    source: str  # tracked_name / tracked_alias / theme / keyword / stock
    matched_term: str


@dataclass
class RepairResult:
    """修复操作结果。"""

    repaired: int = 0
    unchanged: int = 0
    unmatched: int = 0
    skipped: int = 0
    low_confidence: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)


class ClsWatchRepairService:
    """CLS 看盘数据板块归属修复服务。

    对空 sectors 的 CLS watch 行，从本地证据推断板块归属：
    1. 已跟踪板块名称精确匹配（高置信度）
    2. 已跟踪板块别名匹配（高置信度）
    3. 主题词典成员匹配（中置信度）
    4. 已接受学习词条匹配（中置信度）
    5. 标题/内容关键词匹配（低置信度）
    6. 股票关联匹配（低置信度）

    已有非空 sectors 的行保留不变。
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def repair_window(
        self,
        end_date: date,
        window_days: int = 10,
    ) -> RepairResult:
        """修复指定时间窗口内空 sectors 的 CLS 看盘记录。

        Args:
            end_date: 窗口结束日期
            window_days: 回看天数

        Returns:
            修复结果统计
        """
        start_date = end_date - timedelta(days=window_days)
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

        # 构建匹配索引
        tracked_index = await self._build_tracked_index()
        theme_index = await self._build_theme_index()
        stock_to_sectors = await self._build_stock_to_sectors_map(start_ts, end_ts)

        # 查询窗口内所有看盘记录
        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData)
                .where(CLSWatchData.ctime >= start_ts)
                .where(CLSWatchData.ctime <= end_ts)
            )
            watch_items = list(result.scalars().all())

        repair_result = RepairResult()

        async with self.db.get_session() as session:
            for item in watch_items:
                # 保留已有非空 sectors
                existing_sectors = self._parse_sectors(item.sectors)
                if existing_sectors:
                    repair_result.unchanged += 1
                    continue

                # 从本地证据推断板块归属
                matches = self._attribute_sectors(
                    item, tracked_index, theme_index, stock_to_sectors,
                )

                if not matches:
                    repair_result.unmatched += 1
                    continue

                # 按置信度分组
                high_matches = [m for m in matches if m.confidence == CONFIDENCE_HIGH]
                medium_matches = [m for m in matches if m.confidence == CONFIDENCE_MEDIUM]
                low_matches = [m for m in matches if m.confidence == CONFIDENCE_LOW]

                # 去重板块名（高置信度优先）
                chosen: dict[str, AttributionMatch] = {}
                for m in high_matches:
                    key = SectorIdentity.comparison_key(m.sector_name)
                    if key not in chosen:
                        chosen[key] = m
                for m in medium_matches:
                    key = SectorIdentity.comparison_key(m.sector_name)
                    if key not in chosen:
                        chosen[key] = m

                has_low = False
                for m in low_matches:
                    key = SectorIdentity.comparison_key(m.sector_name)
                    if key not in chosen:
                        chosen[key] = m
                        has_low = True

                if not chosen:
                    repair_result.unmatched += 1
                    continue

                # 写入 sectors
                sector_names = list(dict.fromkeys(
                    m.sector_name for m in chosen.values()
                ))
                new_sectors_json = json.dumps(sector_names, ensure_ascii=False)

                # 重新查询以在此 session 中更新
                result = await session.execute(
                    select(CLSWatchData).where(CLSWatchData.id == item.id)
                )
                db_item = result.scalar_one_or_none()
                if db_item:
                    db_item.sectors = new_sectors_json
                    await session.flush()
                    repair_result.repaired += 1

                    if has_low:
                        repair_result.low_confidence += 1

                    repair_result.details.append({
                        "watch_id": item.watch_id,
                        "title": item.title,
                        "sectors": sector_names,
                        "matches": [
                            {
                                "sector": m.sector_name,
                                "confidence": m.confidence,
                                "source": m.source,
                                "matched_term": m.matched_term,
                            }
                            for m in chosen.values()
                        ],
                    })
                else:
                    repair_result.skipped += 1

        logger.info(
            "CLS watch repair: %d repaired, %d unchanged, %d unmatched, %d low-confidence",
            repair_result.repaired,
            repair_result.unchanged,
            repair_result.unmatched,
            repair_result.low_confidence,
        )
        return repair_result

    def _attribute_sectors(
        self,
        item: CLSWatchData,
        tracked_index: dict[str, str],
        theme_index: dict[str, str],
        stock_to_sectors: dict[str, list[str]],
    ) -> list[AttributionMatch]:
        """从本地证据推断单条看盘记录的板块归属。"""
        matches: list[AttributionMatch] = []
        seen_keys: set[str] = set()

        def _add(match: AttributionMatch) -> None:
            key = (SectorIdentity.comparison_key(match.sector_name), match.confidence)
            if key not in seen_keys:
                seen_keys.add(key)
                matches.append(match)

        title = item.title or ""
        content = item.content or ""
        text = f"{title} {content}"

        # 1. 已跟踪板块名称/别名精确匹配
        for word in self._tokenize(text):
            key = SectorIdentity.comparison_key(word)
            if key in tracked_index:
                _add(AttributionMatch(
                    sector_name=tracked_index[key],
                    confidence=CONFIDENCE_HIGH,
                    source="tracked_name",
                    matched_term=word,
                ))

        # 2. 主题词典/已接受学习词条匹配
        for word in self._tokenize(text):
            key = SectorIdentity.comparison_key(word)
            if key in theme_index:
                _add(AttributionMatch(
                    sector_name=theme_index[key],
                    confidence=CONFIDENCE_MEDIUM,
                    source="theme",
                    matched_term=word,
                ))

        # 3. 标题/内容关键词匹配（低置信度）
        for word in self._tokenize(text):
            key = SectorIdentity.comparison_key(word)
            # 跳过太短的词
            if len(key) < 2:
                continue
            # 检查是否匹配已跟踪板块名（部分包含）
            for tracked_key, tracked_name in tracked_index.items():
                if key in tracked_key or tracked_key in key:
                    if len(key) >= 2 and tracked_key != key:
                        _add(AttributionMatch(
                            sector_name=tracked_name,
                            confidence=CONFIDENCE_LOW,
                            source="keyword",
                            matched_term=word,
                        ))

        # 4. 股票关联匹配
        item_stocks = json.loads(item.stocks) if item.stocks else []
        for stock_name in item_stocks:
            stock_key = stock_name.strip()
            if stock_key in stock_to_sectors:
                for sector_name in stock_to_sectors[stock_key]:
                    _add(AttributionMatch(
                        sector_name=sector_name,
                        confidence=CONFIDENCE_LOW,
                        source="stock",
                        matched_term=stock_name,
                    ))

        return matches

    @staticmethod
    def _parse_sectors(sectors_json: str | None) -> list[str]:
        """解析 sectors JSON，返回列表。"""
        if not sectors_json:
            return []
        try:
            parsed = json.loads(sectors_json)
            if isinstance(parsed, list) and len(parsed) > 0:
                return [s for s in parsed if isinstance(s, str) and s.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单中文分词：按标点和空白切分，保留 2+ 字符片段。"""
        import re
        segments = re.split(r"[\s,，、；;。！!？?：:·\-—|]+", text)
        # 保留原始片段和 2-gram
        tokens: list[str] = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if len(seg) >= 2:
                tokens.append(seg)
            # 对长片段生成 2-4 gram 滑动窗口
            if len(seg) >= 3:
                for n in range(2, min(5, len(seg) + 1)):
                    for i in range(len(seg) - n + 1):
                        tokens.append(seg[i:i + n])
        return tokens

    async def _build_tracked_index(self) -> dict[str, str]:
        """构建 comparison_key → canonical_name 索引（含别名）。"""
        index: dict[str, str] = {}
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.status == "tracked")
            )
            sectors = list(result.scalars().all())

        for sector in sectors:
            key = SectorIdentity.comparison_key(sector.canonical_name)
            index[key] = sector.canonical_name
            if sector.aliases:
                try:
                    aliases = json.loads(sector.aliases)
                    for alias in aliases:
                        alias_key = SectorIdentity.comparison_key(alias)
                        index[alias_key] = sector.canonical_name
                except (json.JSONDecodeError, TypeError):
                    pass

        return index

    async def _build_theme_index(self) -> dict[str, str]:
        """构建主题词典 comparison_key → theme_name 索引。"""
        from src.services.theme_registry import ThemeRegistryService

        service = ThemeRegistryService(self.db)
        registry = await service.get_registry()

        index: dict[str, str] = {}
        for theme_name, entry in registry.themes.items():
            for member in entry.members:
                key = SectorIdentity.comparison_key(member)
                if key not in registry.noise_terms and key not in registry.disabled_terms:
                    index[key] = theme_name
            for alias in entry.aliases:
                key = SectorIdentity.comparison_key(alias)
                if key not in registry.noise_terms and key not in registry.disabled_terms:
                    index[key] = theme_name

        return index

    async def _build_stock_to_sectors_map(
        self,
        start_ts: int,
        end_ts: int,
    ) -> dict[str, list[str]]:
        """从已有看盘记录中构建 stock_name → [sector_names] 映射。

        只使用同时有 stocks 和 sectors 的记录作为映射源。
        """
        mapping: dict[str, list[str]] = defaultdict(list)
        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData)
                .where(CLSWatchData.ctime >= start_ts)
                .where(CLSWatchData.ctime <= end_ts)
                .where(CLSWatchData.stocks.isnot(None))
                .where(CLSWatchData.sectors.isnot(None))
            )
            items = result.scalars().all()

        for item in items:
            try:
                stocks = json.loads(item.stocks) if item.stocks else []
                sectors = json.loads(item.sectors) if item.sectors else []
                if not stocks or not sectors:
                    continue
                sector_names = [s for s in sectors if isinstance(s, str) and s.strip()]
                for stock_name in stocks:
                    if isinstance(stock_name, str) and stock_name.strip():
                        existing = mapping.get(stock_name.strip(), [])
                        for s in sector_names:
                            if s not in existing:
                                existing.append(s)
                        mapping[stock_name.strip()] = existing
            except (json.JSONDecodeError, TypeError):
                pass

        return dict(mapping)
