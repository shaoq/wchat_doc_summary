"""daily_kline 表的读写 Repository。

盘后管道批量 upsert 写入；本地聚合层按交易日读取。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.models.schema import DailyKline

logger = logging.getLogger(__name__)


class DailyKlineRepository:
    """daily_kline 数据访问。

    db 需提供 `async get_session()` 上下文管理器（如 src.storage.database.Database）。
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    async def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """批量 upsert 日K行（symbol+trade_date 冲突时更新）。返回处理行数。"""
        if not rows:
            return 0
        stmt = sqlite_insert(DailyKline).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "trade_date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "amount": stmt.excluded.amount,
                # change_pct 依赖序列前值，增量时首根为 None：coalesce 保留已有值
                "change_pct": func.coalesce(stmt.excluded.change_pct, DailyKline.change_pct),
            },
        )
        async with self.db.get_session() as session:
            await session.execute(stmt)
        return len(rows)

    async def get_by_date(self, trade_date: date) -> list[DailyKline]:
        """按交易日查全部日K（聚合用）。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(DailyKline).where(DailyKline.trade_date == trade_date)
            )
            return list(result.scalars().all())

    async def latest_date(self) -> date | None:
        """本地最新日K交易日（增量判断用）。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(DailyKline.trade_date)
                .order_by(DailyKline.trade_date.desc())
                .limit(1)
            )
            row = result.first()
            return row[0] if row else None
