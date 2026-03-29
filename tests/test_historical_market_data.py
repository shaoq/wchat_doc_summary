"""历史交易日市场总结测试 - 验证 MarketAnalyzer 对历史交易日的数据收集行为。

测试场景基于 spec market-data-cache/spec.md，覆盖：
1. 历史交易日缓存命中
2. 历史交易日无缓存，应报告不可用
3. 历史交易日 + --force，应报告不支持
4. 离线模式无缓存
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.market_analyzer import MarketAnalyzer


HISTORICAL_DATE = date(2024, 3, 15)

SAMPLE_CACHED_DATA = {
    "indices": {
        "sh": {"name": "上证指数", "close": 3085.50, "change": 0.0123},
        "sz": {"name": "深证成指", "close": 9567.32, "change": -0.0045},
        "cy": {"name": "创业板指", "close": 1876.44, "change": 0.0078},
    },
    "volume": {
        "sh_volume": 4523.56,
        "sz_volume": 5678.90,
        "total_volume": 10202.46,
    },
    "statistics": {
        "up_count": 3250,
        "down_count": 1520,
        "flat_count": 280,
    },
    "sectors": {
        "top_sectors": [
            {"name": "半导体", "code": "BK1036", "change": 0.0356},
        ],
        "bottom_sectors": [
            {"name": "房地产", "code": "BK0451", "change": -0.0212},
        ],
    },
    "limit_up": [
        {"name": "测试股票", "code": "000001", "change": 0.10, "limit_days": 2, "industry": "半导体"},
    ],
    "fetch_time": "2024-03-15T15:30:00",
    "cached": True,
}


@pytest.fixture
def mock_db():
    """创建模拟数据库。"""
    db = MagicMock()
    db.get_session = AsyncMock()
    return db


@pytest.fixture
def mock_finance_client():
    """创建模拟财经客户端。"""
    client = MagicMock()
    client.get_all_market_data = AsyncMock(return_value={"indices": {}})
    return client


@pytest.fixture
def analyzer(mock_db, mock_finance_client):
    """创建 MarketAnalyzer 实例，注入 mock 依赖。"""
    with patch('src.services.market_analyzer.FinanceClient', return_value=mock_finance_client):
        return MarketAnalyzer(mock_db, finance_client=mock_finance_client)


class TestHistoricalTradeDateCacheHit:
    """场景 1: 历史交易日缓存命中。"""

    @pytest.mark.asyncio
    async def test_returns_cached_data_for_historical_date(self, analyzer, mock_finance_client):
        """历史交易日有缓存时应返回缓存数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=SAMPLE_CACHED_DATA.copy())

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        assert result["data_source"] == "cache"
        assert result["indices"]["sh"]["name"] == "上证指数"
        assert result["indices"]["sh"]["close"] == 3085.50
        assert result["volume"]["total_volume"] == 10202.46

    @pytest.mark.asyncio
    async def test_does_not_call_finance_api_when_cache_hit(self, analyzer, mock_finance_client):
        """历史交易日缓存命中时不应调用 finance_client.get_all_market_data()。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=SAMPLE_CACHED_DATA.copy())

        await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        mock_finance_client.get_all_market_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_get_cached_with_correct_trade_date(self, analyzer):
        """应使用正确的交易日期查询缓存。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=SAMPLE_CACHED_DATA.copy())

        await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        analyzer._cache_service.get_cached.assert_called_once_with(HISTORICAL_DATE)


class TestHistoricalTradeDateNoCache:
    """场景 2: 历史交易日无缓存，应报告不可用。"""

    @pytest.mark.asyncio
    async def test_returns_error_when_no_cache(self, analyzer):
        """历史交易日无缓存时返回包含 error 字段的结果。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        assert "error" in result
        assert str(HISTORICAL_DATE) in result["error"]
        assert "无可用市场数据" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_empty_structure_on_no_cache(self, analyzer):
        """无缓存时返回空结构数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        assert result["indices"] == {}
        assert result["volume"] == {}
        assert result["statistics"] == {}
        assert result["sectors"] == {}
        assert result["limit_up"] == []
        assert result["data_source"] == "none"

    @pytest.mark.asyncio
    async def test_does_not_call_finance_api_when_no_cache(self, analyzer, mock_finance_client):
        """历史交易日无缓存时不应回退到 finance_client 获取数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        mock_finance_client.get_all_market_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_use_today_data_fallback(self, analyzer, mock_finance_client):
        """历史交易日无缓存时不应使用 today 数据回退。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE)

        # 验证没有调用任何 API 获取当天数据
        mock_finance_client.get_all_market_data.assert_not_called()
        # 验证返回的是 error 而非有效数据
        assert "error" in result


class TestHistoricalTradeDateForceRefresh:
    """场景 3: 历史交易日 + --force，应报告不支持强制刷新。"""

    @pytest.mark.asyncio
    async def test_returns_error_with_force_on_historical_date(self, analyzer):
        """历史交易日使用 --force 时返回包含 error 字段的结果。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE, force=True)

        assert "error" in result
        assert str(HISTORICAL_DATE) in result["error"]
        assert "不支持强制刷新" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_empty_structure_with_force(self, analyzer):
        """历史交易日 --force 时仍返回空结构数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE, force=True)

        assert result["indices"] == {}
        assert result["volume"] == {}
        assert result["statistics"] == {}
        assert result["data_source"] == "none"

    @pytest.mark.asyncio
    async def test_does_not_call_finance_api_with_force(self, analyzer, mock_finance_client):
        """历史交易日 --force 时不应调用 finance_client.get_all_market_data()。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        await analyzer.collect_market_data(trade_date=HISTORICAL_DATE, force=True)

        mock_finance_client.get_all_market_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_uses_cache_if_available(self, analyzer, mock_finance_client):
        """历史交易日 --force 但有缓存时，仍返回缓存数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=SAMPLE_CACHED_DATA.copy())

        result = await analyzer.collect_market_data(trade_date=HISTORICAL_DATE, force=True)

        # 有缓存时仍返回缓存数据（force 对历史日期不跳过缓存）
        assert result["data_source"] == "cache"
        assert result["indices"]["sh"]["name"] == "上证指数"
        mock_finance_client.get_all_market_data.assert_not_called()


class TestOfflineModeNoCache:
    """场景 4: 离线模式无缓存。"""

    @pytest.mark.asyncio
    async def test_returns_error_in_offline_mode_without_cache(self, analyzer):
        """离线模式无缓存时返回包含 error 字段的结果。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(offline=True, trade_date=HISTORICAL_DATE)

        assert "error" in result
        assert "离线模式" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_offline_flag_in_result(self, analyzer):
        """离线模式返回的结果包含 offline=True 标记。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(offline=True, trade_date=HISTORICAL_DATE)

        assert result["offline"] is True

    @pytest.mark.asyncio
    async def test_returns_empty_structure_in_offline_mode(self, analyzer):
        """离线模式无缓存时返回空结构。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        analyzer._cache_service.get_cached = AsyncMock(return_value=None)

        result = await analyzer.collect_market_data(offline=True, trade_date=HISTORICAL_DATE)

        assert result["indices"] == {}
        assert result["volume"] == {}
        assert result["statistics"] == {}
        assert result["sectors"] == {}
        assert result["limit_up"] == []
        assert result["data_source"] == "none"

    @pytest.mark.asyncio
    async def test_offline_with_cache_returns_data(self, analyzer, mock_finance_client):
        """离线模式有缓存时返回缓存数据。"""
        analyzer._is_historical_trade_date = MagicMock(return_value=True)
        cached = SAMPLE_CACHED_DATA.copy()
        analyzer._cache_service.get_cached = AsyncMock(return_value=cached)

        result = await analyzer.collect_market_data(offline=True, trade_date=HISTORICAL_DATE)

        assert result["offline"] is True
        assert result["data_source"] == "cache"
        assert result["indices"]["sh"]["close"] == 3085.50
        mock_finance_client.get_all_market_data.assert_not_called()


class TestIsHistoricalTradeDate:
    """测试 _is_historical_trade_date 的判断逻辑。"""

    @pytest.mark.asyncio
    async def test_date_before_latest_is_historical(self, analyzer):
        """早于最新交易日的日期应被判定为历史日期。"""
        analyzer.get_latest_trade_date = MagicMock(return_value=date(2024, 3, 20))

        assert analyzer._is_historical_trade_date(date(2024, 3, 15)) is True
        assert analyzer._is_historical_trade_date(date(2024, 3, 19)) is True

    @pytest.mark.asyncio
    async def test_date_equals_latest_is_not_historical(self, analyzer):
        """等于最新交易日的日期不应被判定为历史日期。"""
        analyzer.get_latest_trade_date = MagicMock(return_value=date(2024, 3, 20))

        assert analyzer._is_historical_trade_date(date(2024, 3, 20)) is False

    @pytest.mark.asyncio
    async def test_date_after_latest_is_not_historical(self, analyzer):
        """晚于最新交易日的日期不应被判定为历史日期。"""
        analyzer.get_latest_trade_date = MagicMock(return_value=date(2024, 3, 20))

        assert analyzer._is_historical_trade_date(date(2024, 3, 21)) is False
