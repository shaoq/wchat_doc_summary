"""TickFlow Provider——组合盘后管道 + 本地聚合，实现 6 分类。

indices 直接拉指数日K；其余 5 分类从 daily_kline 本地聚合（依赖盘后管道已跑）。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from src.services.market_data_sync_service import MarketDataSyncService

from ..base import (
    BreadthStatistics,
    IndexQuote,
    LimitUpRow,
    MarketDataProvider,
    SectorResult,
    SnapshotRow,
    VolumeData,
)
from .aggregation import LocalAggregator
from .client import get_client

logger = logging.getLogger(__name__)

# 核心指数（与 FinanceClient 上证/深证/创业板口径一致）
_INDEX_SYMBOLS = {"sh": "000001.SH", "sz": "399001.SZ", "cy": "399006.SZ"}
_INDEX_NAMES = {"sh": "上证指数", "sz": "深证成指", "cy": "创业板指"}


class TickFlowProvider(MarketDataProvider):
    """TickFlow free 档市场数据 Provider。"""

    name = "tickflow"
    supports_historical = True  # free 档日K支持按历史日期取数

    def __init__(self, db: Any) -> None:
        self.db = db
        self._sync = MarketDataSyncService(db)
        self._agg = LocalAggregator(db)

    async def _latest_date(self) -> date | None:
        return await self._agg.repo.latest_date()

    async def get_indices(
        self, trade_date: date | None = None
    ) -> dict[str, IndexQuote] | None:
        # 指数直接拉日K（秒级）；trade_date 当前忽略，取最新
        return await asyncio.to_thread(self._fetch_indices)

    @staticmethod
    def _fetch_indices() -> dict[str, IndexQuote] | None:
        tf = get_client()
        result: dict[str, IndexQuote] = {}
        for key, sym in _INDEX_SYMBOLS.items():
            try:
                r = tf.klines.get(sym, period="1d", count=2, as_dataframe=False)
                closes = (r or {}).get("close", [])
                if not closes:
                    continue
                price = closes[-1]
                change: float | None = None
                if len(closes) >= 2 and closes[-2] not in (None, 0):
                    change = (closes[-1] - closes[-2]) / closes[-2]
                result[key] = IndexQuote(name=_INDEX_NAMES[key], price=price, change=change)
            except Exception as e:  # noqa: BLE001
                logger.warning("指数 %s 拉取失败: %s", sym, e)
        return result or None

    async def get_volume(self, trade_date: date | None = None) -> VolumeData | None:
        d = trade_date or await self._latest_date()
        return await self._agg.aggregate_volume(d) if d else None

    async def get_statistics(
        self, trade_date: date | None = None
    ) -> BreadthStatistics | None:
        d = trade_date or await self._latest_date()
        return await self._agg.aggregate_statistics(d) if d else None

    async def get_sectors(
        self, trade_date: date | None = None, top_n: int = 10
    ) -> SectorResult | None:
        d = trade_date or await self._latest_date()
        return await self._agg.aggregate_sectors(d, top_n) if d else None

    async def get_limit_up(
        self, trade_date: date | None = None
    ) -> list[LimitUpRow] | None:
        d = trade_date or await self._latest_date()
        return await self._agg.aggregate_limit_up(d) if d else None

    async def get_snapshot(
        self, trade_date: date | None = None
    ) -> list[SnapshotRow] | None:
        d = trade_date or await self._latest_date()
        return await self._agg.aggregate_snapshot(d) if d else None
