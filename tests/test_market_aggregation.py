"""本地聚合层单测（in-memory db + mock 行业成分）。"""

from contextlib import asynccontextmanager
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.market_providers.tickflow.aggregation import LocalAggregator
from src.models.schema import Base
from src.storage.daily_kline_repository import DailyKlineRepository


class _FakeDB:
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
async def db_repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db = _FakeDB(factory)
    repo = DailyKlineRepository(db)
    # 填 3 只票：2 涨 1 跌，1 只涨停
    d = date(2026, 7, 18)
    await repo.upsert_rows(
        [
            {"symbol": "600000.SH", "trade_date": d, "close": 10.0,
             "change_pct": 0.05, "amount": 1e9},  # 10亿 沪
            {"symbol": "000001.SZ", "trade_date": d, "close": 15.0,
             "change_pct": 0.10, "amount": 2e9},  # 20亿 深，涨停
            {"symbol": "000333.SZ", "trade_date": d, "close": 20.0,
             "change_pct": -0.03, "amount": 3e9},  # 30亿 深，跌
        ]
    )
    yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_aggregate_volume(db_repo):
    agg = LocalAggregator(db_repo)
    v = await agg.aggregate_volume(date(2026, 7, 18))
    assert v is not None
    assert v.sh_volume == pytest.approx(10.0)  # 1e9 / 1e8 = 10 亿
    assert v.sz_volume == pytest.approx(50.0)  # (2e9+3e9)/1e8
    assert v.total_volume == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_aggregate_statistics(db_repo):
    agg = LocalAggregator(db_repo)
    s = await agg.aggregate_statistics(date(2026, 7, 18))
    assert s is not None
    assert s.up_count == 2
    assert s.down_count == 1
    assert s.flat_count == 0


@pytest.mark.asyncio
async def test_aggregate_limit_up(db_repo):
    agg = LocalAggregator(db_repo)
    lu = await agg.aggregate_limit_up(date(2026, 7, 18))
    assert lu is not None
    assert len(lu) == 1  # 仅 000001.SZ (+10%) ≥ 9.9%
    assert lu[0].stock_code == "000001.SZ"


@pytest.mark.asyncio
async def test_aggregate_snapshot(db_repo):
    agg = LocalAggregator(db_repo)
    snap = await agg.aggregate_snapshot(date(2026, 7, 18))
    assert snap is not None
    assert len(snap) == 3


@pytest.mark.asyncio
async def test_aggregate_sectors_with_mock_industry(db_repo, monkeypatch):
    """mock SW1 行业成分，验证行业涨幅聚合（均值）。"""
    agg = LocalAggregator(db_repo)
    # 直接注入 industry_map，跳过网络
    agg._industry_map = {
        "SW1_A": {"name": "行业A", "symbols": ["600000.SH", "000001.SZ"]},  # (0.05+0.10)/2
        "SW1_B": {"name": "行业B", "symbols": ["000333.SZ"]},  # -0.03
    }
    result = await agg.aggregate_sectors(date(2026, 7, 18), top_n=10)
    assert result is not None
    top = result.top_sectors
    assert top[0].sector_name == "行业A"  # 均值 0.075 最高
    assert top[0].change_pct == pytest.approx(0.075)
    bottom = result.bottom_sectors
    assert any(s.sector_name == "行业B" for s in bottom)


@pytest.mark.asyncio
async def test_aggregate_empty_date(db_repo):
    """无数据的交易日返回 None。"""
    agg = LocalAggregator(db_repo)
    assert await agg.aggregate_volume(date(2020, 1, 1)) is None
    assert await agg.aggregate_statistics(date(2020, 1, 1)) is None
