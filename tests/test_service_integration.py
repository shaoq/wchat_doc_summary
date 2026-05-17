"""关键服务最小数据库级集成测试。"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from src.models.schema import Auth, Feed, MarketIndex, MarketStatistics, MarketVolume
from src.services.auth import AuthService
from src.services.market_data_cache_service import MarketDataCacheService
from src.services.subscription import SubscriptionService
from src.storage.database import Database


@pytest.mark.asyncio
async def test_subscription_service_persists_feed(integration_db: Database) -> None:
    """订阅服务会持久化 feed。"""
    service = SubscriptionService(integration_db)
    feed, _ = await service.add_subscription("MP_WXS_test", "测试公众号", "简介", "cover")

    async with integration_db.get_session() as session:
        result = await session.execute(select(Feed).where(Feed.mp_id == "MP_WXS_test"))
        db_feed = result.scalar_one_or_none()

    assert db_feed is not None
    assert db_feed.id == feed.id
    assert db_feed.name == "测试公众号"


@pytest.mark.asyncio
async def test_auth_service_persists_successful_token(integration_db: Database) -> None:
    """认证服务会保存成功登录 token。"""
    weread_client = MagicMock()
    weread_client.get_login_result = AsyncMock(
        return_value={
            "status": "success",
            "message": "登录成功",
            "token": "token_123",
            "user_info": {"name": "tester"},
        }
    )
    weread_client.set_token = MagicMock()

    service = AuthService(weread_client, integration_db)
    result = await service.check_login("login_123")

    assert result["success"] is True

    async with integration_db.get_session() as session:
        auth_result = await session.execute(select(Auth).where(Auth.token == "token_123"))
        auth = auth_result.scalar_one_or_none()

    assert auth is not None
    assert auth.username == "tester"
    assert auth.status == 1


@pytest.mark.asyncio
async def test_market_data_cache_service_round_trip(integration_db: Database) -> None:
    """缓存服务能保存并读回真实 ORM 数据。"""
    service = MarketDataCacheService(integration_db)
    trade_date = date.today() - timedelta(days=1)

    await service.save_market_data(
        trade_date,
        {
            "indices": {
                "sh": {"name": "上证指数", "price": 3000.0, "change": 0.01},
            },
            "volume": {"sh_volume": 1000.0, "sz_volume": 2000.0, "total_volume": 3000.0},
            "statistics": {"up_count": 10, "down_count": 20, "flat_count": 30},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
        },
    )

    cached = await service.get_cached(trade_date)

    assert cached is not None
    assert cached["indices"]["sh"]["name"] == "上证指数"
    assert cached["volume"]["total_volume"] == 3000.0
    assert cached["statistics"]["up_count"] == 10

    async with integration_db.get_session() as session:
        index_result = await session.execute(select(MarketIndex).where(MarketIndex.trade_date == trade_date))
        volume_result = await session.execute(select(MarketVolume).where(MarketVolume.trade_date == trade_date))
        stats_result = await session.execute(select(MarketStatistics).where(MarketStatistics.trade_date == trade_date))

    assert index_result.scalar_one_or_none() is not None
    assert volume_result.scalar_one_or_none() is not None
    assert stats_result.scalar_one_or_none() is not None
