"""daily_kline repository 单测（in-memory sqlite）。"""

from contextlib import asynccontextmanager
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.schema import Base
from src.storage.daily_kline_repository import DailyKlineRepository


class _FakeDB:
    """仅提供 get_session 的测试 DB。"""

    def __init__(self, factory):
        self._factory = factory

    @asynccontextmanager
    async def get_session(self):
        async with self._factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield _FakeDB(factory)
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_and_get_by_date(db):
    repo = DailyKlineRepository(db)
    d = date(2026, 7, 18)
    rows = [
        {"symbol": "600000.SH", "trade_date": d, "close": 10.0, "change_pct": 0.01},
        {"symbol": "000001.SZ", "trade_date": d, "close": 15.0, "change_pct": -0.02},
    ]
    assert await repo.upsert_rows(rows) == 2
    got = await repo.get_by_date(d)
    assert len(got) == 2


@pytest.mark.asyncio
async def test_upsert_empty(db):
    repo = DailyKlineRepository(db)
    assert await repo.upsert_rows([]) == 0


@pytest.mark.asyncio
async def test_upsert_conflict_updates(db):
    """同 symbol+date 二次 upsert 覆盖旧值。"""
    repo = DailyKlineRepository(db)
    d = date(2026, 7, 18)
    await repo.upsert_rows([{"symbol": "600000.SH", "trade_date": d, "close": 10.0}])
    await repo.upsert_rows(
        [{"symbol": "600000.SH", "trade_date": d, "close": 11.0, "change_pct": 0.05}]
    )
    got = await repo.get_by_date(d)
    assert len(got) == 1
    assert got[0].close == 11.0
    assert got[0].change_pct == 0.05


@pytest.mark.asyncio
async def test_latest_date(db):
    repo = DailyKlineRepository(db)
    assert await repo.latest_date() is None
    await repo.upsert_rows(
        [
            {"symbol": "600000.SH", "trade_date": date(2026, 7, 17)},
            {"symbol": "600000.SH", "trade_date": date(2026, 7, 18)},
        ]
    )
    assert await repo.latest_date() == date(2026, 7, 18)
