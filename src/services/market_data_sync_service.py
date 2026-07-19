"""盘后日K管道——批量拉全市场日K写入 daily_kline。

free 档无全市场实时快照，所有聚合指标（涨跌家数/成交额/行业涨幅/涨停池/快照）
靠本表本地算。SDK 同步调用经 asyncio.to_thread 避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.api.market_providers.tickflow.client import get_client
from src.api.market_providers.tickflow.rate_limits import chunked, sleep_between_batches
from src.storage.daily_kline_repository import DailyKlineRepository

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_EXCHANGES = ["SH", "SZ", "BJ"]
_BATCH_SIZE = 100
_RPM = 60


class MarketDataSyncService:
    """盘后日K管道：拉全市场标的 → 批量日K → 写 daily_kline。"""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.repo = DailyKlineRepository(db)

    async def sync(self, count: int = 1) -> dict[str, int]:
        """同步全市场日K。

        Args:
            count: 每只票目标写入的日K根数（增量=1，回填=N）。内部多拉 1 根用于
                   算最新一根的 change_pct（实际请求 count+1）。

        Returns:
            {"symbols": 标的数, "rows": 写入行数}
        """
        symbols = await asyncio.to_thread(self._fetch_all_symbols)
        if not symbols:
            logger.warning("盘后管道：未取到标的列表，终止")
            return {"symbols": 0, "rows": 0}

        # 多拉 1 根：最新一根的 change_pct 需要前一日 close
        rows = await asyncio.to_thread(self._fetch_daily_klines, symbols, count + 1)
        written = await self.repo.upsert_rows(rows)
        logger.info("盘后日K同步完成: %d 标的, %d 行写入", len(symbols), written)
        return {"symbols": len(symbols), "rows": written}

    @staticmethod
    def _retry(
        fn: Callable[[], Any], label: str, attempts: int = 3, backoff: float = 1.0
    ) -> Any:
        """瞬时错误（SSL EOF / 网络抖动）退避重试。全失败返回 None。"""
        for i in range(attempts):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001
                logger.warning("%s 第 %d/%d 次失败: %s", label, i + 1, attempts, e)
                if i < attempts - 1:
                    time.sleep(backoff * (i + 1))
        return None

    def _fetch_all_symbols(self) -> list[str]:
        """拉全市场 A 股标的列表（SH/SZ/BJ）。"""
        tf = get_client()
        syms: list[str] = []
        for ex in _EXCHANGES:
            items = self._retry(
                lambda ex=ex: tf.exchanges.get_instruments(ex, instrument_type="stock"),
                f"instruments({ex})",
            )
            for it in (items or []):
                s = it.get("symbol") if isinstance(it, dict) else getattr(it, "symbol", None)
                if s:
                    syms.append(s)
        return syms

    def _fetch_daily_klines(self, symbols: list[str], count: int) -> list[dict[str, Any]]:
        """批量拉日K（分批 100，60rpm 节奏），normalize 成 daily_kline rows。"""
        tf = get_client()
        rows: list[dict[str, Any]] = []
        batches = chunked(symbols, _BATCH_SIZE)
        for i, batch in enumerate(batches):
            sleep_between_batches(i, _RPM)
            raw = self._retry(
                lambda b=batch, c=count: tf.klines.batch(
                    b,
                    period="1d",
                    count=c,
                    adjust="none",
                    as_dataframe=False,
                    show_progress=False,
                ),
                f"klines.batch {i + 1}/{len(batches)}",
            )
            if raw is None:
                continue
            rows.extend(self._normalize(raw))
        return rows

    @staticmethod
    def _normalize(batch_result: dict) -> list[dict[str, Any]]:
        """SDK batch 返回 → daily_kline rows（change_pct 从 close 序列本地算）。"""
        rows: list[dict[str, Any]] = []
        for symbol, data in (batch_result or {}).items():
            if not isinstance(data, dict):
                continue
            timestamps = data.get("timestamp") or []
            closes = data.get("close") or []
            for idx in range(len(timestamps)):
                close_i = _idx(closes, idx)
                close_prev = _idx(closes, idx - 1) if idx > 0 else None
                change_pct: float | None = None
                if close_prev not in (None, 0) and close_i is not None:
                    change_pct = (close_i - close_prev) / close_prev
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": _ms_to_date(timestamps[idx]),
                        "open": _idx(data.get("open"), idx),
                        "high": _idx(data.get("high"), idx),
                        "low": _idx(data.get("low"), idx),
                        "close": close_i,
                        "volume": _idx(data.get("volume"), idx),
                        "amount": _idx(data.get("amount"), idx),
                        "change_pct": change_pct,
                    }
                )
        return rows


def _ms_to_date(ms: int) -> date:
    """毫秒时间戳（UTC epoch）→ CST 交易日。"""
    return datetime.fromtimestamp(ms / 1000, tz=_CST).date()


def _idx(lst: list | None, i: int) -> float | None:
    if not lst or i < 0 or i >= len(lst):
        return None
    v = lst[i]
    return float(v) if v is not None else None
