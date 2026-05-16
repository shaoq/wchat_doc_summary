"""回归测试 - 验证 historical market-summary --force 不获取实时数据。"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.market_analyzer import MarketAnalyzer


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.get_session = MagicMock()
    return db


class TestHistoricalForceDoesNotFetchRealtime:
    """验证 --force 对历史日期不获取实时数据。"""

    @pytest.mark.asyncio
    async def test_force_historical_does_not_call_api(self) -> None:
        """historical --force 不调用 FinanceClient.get_all_market_data。"""
        db = _make_mock_db()
        fc = MagicMock()
        fc.get_all_market_data = AsyncMock()
        analyzer = MarketAnalyzer(db, fc)

        # Mock cache_service.get_cached 返回 None（无缓存）
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        # 使用一个明确的历史日期
        historical_date = date(2026, 5, 10)

        result = await analyzer.collect_market_data(
            offline=False,
            trade_date=historical_date,
            force=True,
        )

        # 不应调用 API
        fc.get_all_market_data.assert_not_called()

        # 应返回 error 状态
        assert result["data_source"] == "none"
        assert "不支持强制刷新" in result["error"]
        assert "backfill" in result["error"]

    @pytest.mark.asyncio
    async def test_historical_no_cache_points_to_backfill(self) -> None:
        """历史日期无缓存时，错误信息指向 backfill 命令。"""
        db = _make_mock_db()
        fc = MagicMock()
        analyzer = MarketAnalyzer(db, fc)

        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        historical_date = date(2026, 5, 10)

        result = await analyzer.collect_market_data(
            offline=False,
            trade_date=historical_date,
            force=False,
        )

        assert result["data_source"] == "none"
        assert "backfill" in result["error"]
        assert "wchat ai market-data backfill" in result["error"]

    @pytest.mark.asyncio
    async def test_historical_with_cache_uses_cache_only(self) -> None:
        """历史日期有缓存时使用缓存，不调用 API。"""
        db = _make_mock_db()
        fc = MagicMock()
        fc.get_all_market_data = AsyncMock()
        analyzer = MarketAnalyzer(db, fc)

        cached_data = {
            "indices": {"sh": {"name": "上证", "close": 3000, "change": 0.01}},
            "volume": {"total_volume": 100},
            "statistics": {"up_count": 100},
            "sectors": {"top_sectors": []},
            "limit_up": [],
        }
        analyzer._cache_service.get_cached = AsyncMock(return_value=cached_data)

        historical_date = date(2026, 5, 10)

        result = await analyzer.collect_market_data(
            offline=False,
            trade_date=historical_date,
            force=True,
        )

        # 不应调用 API
        fc.get_all_market_data.assert_not_called()

        # 应返回缓存数据
        assert result["data_source"] == "cache"
        assert result["indices"]["sh"]["close"] == 3000
