"""本地聚合层——从 daily_kline + 申万行业成分算全市场指标。

free 档无全市场实时快照，所有聚合指标从本地 daily_kline 表算。
行业涨幅用 universes.get 拿 SW1 成分股 + 成分 change_pct 聚合。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from src.storage.daily_kline_repository import DailyKlineRepository

from ..base import (
    BreadthStatistics,
    LimitUpRow,
    SectorResult,
    SectorRow,
    SnapshotRow,
    VolumeData,
)
from .client import get_client

logger = logging.getLogger(__name__)

# 涨停阈值（小数）。主板 10%、创业板/科创板 20%、ST 5%；此处取宽松下限 9.9%，
# task 7 精确化时可按 symbol 前缀/板块规则细化。
_LIMIT_UP_THRESHOLD = 0.099


class LocalAggregator:
    """从本地 daily_kline 表聚合各分类指标。"""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.repo = DailyKlineRepository(db)
        self._industry_map: dict[str, dict[str, Any]] | None = None

    async def aggregate_volume(self, trade_date: date) -> VolumeData | None:
        rows = await self.repo.get_by_date(trade_date)
        if not rows:
            return None
        sh = sum(r.amount or 0.0 for r in rows if r.symbol.endswith(".SH"))
        sz = sum(r.amount or 0.0 for r in rows if r.symbol.endswith(".SZ"))
        return VolumeData(
            sh_volume=sh / 1e8,
            sz_volume=sz / 1e8,
            total_volume=(sh + sz) / 1e8,
        )

    async def aggregate_statistics(self, trade_date: date) -> BreadthStatistics | None:
        rows = await self.repo.get_by_date(trade_date)
        if not rows:
            return None
        up = sum(1 for r in rows if (r.change_pct or 0) > 0)
        down = sum(1 for r in rows if (r.change_pct or 0) < 0)
        flat = sum(1 for r in rows if r.change_pct is not None and r.change_pct == 0)
        return BreadthStatistics(up_count=up, down_count=down, flat_count=flat)

    async def aggregate_snapshot(self, trade_date: date) -> list[SnapshotRow] | None:
        rows = await self.repo.get_by_date(trade_date)
        if not rows:
            return None
        return [
            SnapshotRow(
                symbol=r.symbol,
                name=None,
                price=r.close,
                change_pct=r.change_pct,
                volume=r.volume,
                amount=r.amount,
            )
            for r in rows
        ]

    async def aggregate_limit_up(self, trade_date: date) -> list[LimitUpRow] | None:
        rows = await self.repo.get_by_date(trade_date)
        if not rows:
            return None
        result: list[LimitUpRow] = []
        for r in rows:
            if (r.change_pct or 0) >= _LIMIT_UP_THRESHOLD:
                # daily_kline 不存 name，留给 Provider 层补（task 7）
                result.append(
                    LimitUpRow(
                        stock_code=r.symbol, stock_name="", change_pct=r.change_pct
                    )
                )
        return result

    async def aggregate_sectors(
        self, trade_date: date, top_n: int = 10
    ) -> SectorResult | None:
        rows = await self.repo.get_by_date(trade_date)
        if not rows:
            return None
        industry_map = await self._get_industry_map()
        if not industry_map:
            return None

        pct_map = {r.symbol: r.change_pct for r in rows}
        ranked: list[tuple[str, str, float]] = []  # (uid, name, avg_pct)
        for uid, info in industry_map.items():
            pcts = [
                pct_map[s]
                for s in info["symbols"]
                if s in pct_map and pct_map[s] is not None
            ]
            if not pcts:
                continue
            ranked.append((uid, info["name"], sum(pcts) / len(pcts)))

        ranked.sort(key=lambda x: x[2], reverse=True)
        top = [SectorRow(sector_code=c, sector_name=n, change_pct=p) for c, n, p in ranked[:top_n]]
        bottom_n = ranked[-top_n:] if len(ranked) > top_n else ranked
        bottom = [SectorRow(sector_code=c, sector_name=n, change_pct=p) for c, n, p in bottom_n]
        return SectorResult(top_sectors=top, bottom_sectors=bottom)

    async def _get_industry_map(self) -> dict[str, dict[str, Any]]:
        """SW1 行业成分映射：实例缓存 → DB 持久缓存 → 在线拉取并落库。"""
        if self._industry_map is not None:
            return self._industry_map

        # 1. 读 DB 持久缓存
        cached = await self._load_industry_map_db()
        if cached:
            self._industry_map = cached
            return cached

        # 2. miss：在线拉取（带整体超时兜底），成功后落库
        try:
            mapping = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_industry_map), timeout=90
            )
        except asyncio.TimeoutError:
            logger.warning("拉取 SW1 行业成分超时(90s)，sectors 本轮可能不可用")
            mapping = {}
        if mapping:
            await self._save_industry_map_db(mapping)
        self._industry_map = mapping
        return mapping

    async def _load_industry_map_db(self) -> dict[str, dict[str, Any]] | None:
        """从 industry_members 表读缓存映射。"""
        from sqlalchemy import select

        from src.models.schema import IndustryMember

        try:
            async with self.db.get_session() as session:
                result = await session.execute(select(IndustryMember))
                rows = result.scalars().all()
        except Exception as e:  # noqa: BLE001
            logger.warning("读 industry_members 失败: %s", e)
            return None
        if not rows:
            return None
        mapping: dict[str, dict[str, Any]] = {}
        for r in rows:
            mapping.setdefault(r.industry_code, {"name": r.industry_name, "symbols": []})[
                "symbols"
            ].append(r.symbol)
        return mapping

    async def _save_industry_map_db(self, mapping: dict[str, dict[str, Any]]) -> None:
        """全量替换写入 industry_members（日更语义）。"""
        from sqlalchemy import delete

        from src.models.schema import IndustryMember

        try:
            async with self.db.get_session() as session:
                await session.execute(delete(IndustryMember))
                objs = [
                    IndustryMember(
                        industry_code=uid, industry_name=info["name"], symbol=sym
                    )
                    for uid, info in mapping.items()
                    for sym in info["symbols"]
                ]
                session.add_all(objs)
        except Exception as e:  # noqa: BLE001
            logger.warning("写 industry_members 失败: %s", e)

    @staticmethod
    def _fetch_industry_map() -> dict[str, dict[str, Any]]:
        """从 TickFlow free 拉 SW1 行业成分（universes.batch 单请求，避免限流）。"""
        tf = get_client()
        try:
            unis = tf.universes.list()
        except Exception as e:  # noqa: BLE001
            logger.warning("universes.list failed: %s", e)
            return {}

        sw1 = [
            (u.get("id", ""), u.get("name", ""))
            if isinstance(u, dict)
            else (getattr(u, "id", ""), getattr(u, "name", ""))
            for u in unis or []
        ]
        sw1 = [(uid, name) for uid, name in sw1 if uid.startswith("CN_Equity_SW1")]
        if not sw1:
            return {}

        uids = [uid for uid, _ in sw1]
        name_map = {uid: name for uid, name in sw1}

        try:
            detail = tf.universes.batch(uids)
        except Exception as e:  # noqa: BLE001
            logger.warning("universes.batch(%d SW1) failed: %s", len(uids), e)
            return {}

        mapping: dict[str, dict[str, Any]] = {}
        for uid in uids:
            entry = detail.get(uid) if isinstance(detail, dict) else None
            syms = entry.get("symbols", []) if isinstance(entry, dict) else []
            if syms:
                mapping[uid] = {"name": name_map.get(uid, ""), "symbols": list(syms)}
        return mapping
