"""测试 MarketSector 和 LimitUpStock 模型的唯一约束。"""

import pytest
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.models.schema import Base, MarketSector, LimitUpStock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
async def async_engine():
    """创建异步引擎。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    """异步数据库会话。"""
    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session


class TestMarketSectorModel:
    """测试 MarketSector 模型。"""

    async def test_create_market_sector(self, async_session: AsyncSession):
        """测试创建 MarketSector 记录。"""
        sector = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0001",
            sector_name="测试板块",
            change_pct=2.5,
            amount=1000000.0,
            main_inflow=50000.0,
        )
        async_session.add(sector)
        await async_session.commit()

        result = await async_session.execute(
            select(MarketSector).where(MarketSector.sector_code == "BK0001")
        )
        saved = result.scalar_one()
        assert saved.sector_name == "测试板块"
        assert saved.change_pct == 2.5

    async def test_unique_constraint_same_date_and_code(
        self, async_session: AsyncSession
    ):
        """测试同一日期和板块代码的唯一约束。"""
        sector1 = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0002",
            sector_name="板块1",
        )
        async_session.add(sector1)
        await async_session.commit()

        sector2 = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0002",
            sector_name="板块2",
        )
        async_session.add(sector2)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_same_code_different_date(self, async_session: AsyncSession):
        """测试相同板块代码但不同日期可以插入。"""
        sector1 = MarketSector(
            trade_date=date(2026, 3, 25),
            sector_code="BK0003",
            sector_name="板块A",
        )
        sector2 = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0003",
            sector_name="板块B",
        )
        async_session.add(sector1)
        async_session.add(sector2)
        await async_session.commit()

        result = await async_session.execute(
            select(MarketSector).where(MarketSector.sector_code == "BK0003")
        )
        saved = result.scalars().all()
        assert len(saved) == 2

    async def test_same_date_different_code(self, async_session: AsyncSession):
        """测试相同日期但不同板块代码可以插入。"""
        sector1 = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0004",
            sector_name="板块X",
        )
        sector2 = MarketSector(
            trade_date=date(2026, 3, 26),
            sector_code="BK0005",
            sector_name="板块Y",
        )
        async_session.add(sector1)
        async_session.add(sector2)
        await async_session.commit()

        result = await async_session.execute(
            select(MarketSector).where(MarketSector.trade_date == date(2026, 3, 26))
        )
        saved = result.scalars().all()
        assert len(saved) == 2


class TestLimitUpStockModel:
    """测试 LimitUpStock 模型。"""

    async def test_create_limit_up_stock(self, async_session: AsyncSession):
        """测试创建 LimitUpStock 记录。"""
        stock = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000001",
            stock_name="测试股票",
            change_pct=10.0,
            limit_days=1,
            industry="金融",
        )
        async_session.add(stock)
        await async_session.commit()

        result = await async_session.execute(
            select(LimitUpStock).where(LimitUpStock.stock_code == "000001")
        )
        saved = result.scalar_one()
        assert saved.stock_name == "测试股票"
        assert saved.change_pct == 10.0

    async def test_unique_constraint_same_date_and_code(
        self, async_session: AsyncSession
    ):
        """测试同一日期和股票代码的唯一约束。"""
        stock1 = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000002",
            stock_name="股票1",
        )
        async_session.add(stock1)
        await async_session.commit()

        stock2 = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000002",
            stock_name="股票2",
        )
        async_session.add(stock2)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_same_code_different_date(self, async_session: AsyncSession):
        """测试相同股票代码但不同日期可以插入。"""
        stock1 = LimitUpStock(
            trade_date=date(2026, 3, 25),
            stock_code="000003",
            stock_name="股票A",
        )
        stock2 = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000003",
            stock_name="股票B",
        )
        async_session.add(stock1)
        async_session.add(stock2)
        await async_session.commit()

        result = await async_session.execute(
            select(LimitUpStock).where(LimitUpStock.stock_code == "000003")
        )
        saved = result.scalars().all()
        assert len(saved) == 2

    async def test_same_date_different_code(self, async_session: AsyncSession):
        """测试相同日期但不同股票代码可以插入。"""
        stock1 = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000004",
            stock_name="股票X",
        )
        stock2 = LimitUpStock(
            trade_date=date(2026, 3, 26),
            stock_code="000005",
            stock_name="股票Y",
        )
        async_session.add(stock1)
        async_session.add(stock2)
        await async_session.commit()

        result = await async_session.execute(
            select(LimitUpStock).where(LimitUpStock.trade_date == date(2026, 3, 26))
        )
        saved = result.scalars().all()
        assert len(saved) == 2
