"""FinanceClient 数据契约测试。

测试 FinanceClient 对外输出的数据结构是否符合统一 contract：
- 指数数据: dict[key -> {name, close, change}]，无数据返回 {}
- 成交额数据: {sh_volume, sz_volume, total_volume}，无数据返回零值
- 涨跌统计: {up_count, down_count, flat_count}，无数据返回零值
- 板块数据: {top_sectors, bottom_sectors}，无数据返回空榜单
- 涨停股: list[dict]，无数据返回 []
- 聚合数据: {indices, volume, statistics, sectors, limit_up, fetch_time}
"""

from datetime import date
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.finance import EastMoneyCurlClient, FinanceClient


@pytest.fixture
def finance_client():
    """创建 FinanceClient 实例。"""
    return FinanceClient()


@pytest.fixture
def mock_indices_data():
    """模拟指数数据。"""
    return {
        "sh": {"name": "上证指数", "close": 3881.28, "change": 0.0178},
        "sz": {"name": "深证成指", "close": 13536.56, "change": 0.0143},
        "cy": {"name": "创业板指", "close": 3251.55, "change": 0.0050},
    }


@pytest.fixture
def mock_volume_data():
    """模拟成交额数据。"""
    return {
        "sh_volume": 5000.5,
        "sz_volume": 6500.3,
        "total_volume": 11500.8,
    }


@pytest.fixture
def mock_statistics_data():
    """模拟涨跌统计数据。"""
    return {
        "up_count": 2500,
        "down_count": 2100,
        "flat_count": 400,
    }


@pytest.fixture
def mock_stock_snapshot():
    """模拟全市场股票快照（东方财富格式）。"""
    return [
        {"f12": "600000", "f14": "浦发银行", "f3": 1.83, "f6": 611456194.0},
        {"f12": "600036", "f14": "招商银行", "f3": 0.15, "f6": 2408674586.0},
        {"f12": "000001", "f14": "平安银行", "f3": 3.83, "f6": 1744746707.7},
        {"f12": "000002", "f14": "万科A", "f3": -0.24, "f6": 371679205.05},
        {"f12": "300001", "f14": "特锐德", "f3": -1.5, "f6": 1275000000.0},
        {"f12": "300002", "f14": "神州泰岳", "f3": 0.0, "f6": 360000000.0},
    ]


# ── 指数数据 contract ──────────────────────────────────────────


class TestIndexDataContract:
    """指数数据契约测试。"""

    @pytest.mark.asyncio
    async def test_normal_returns_dict_with_keys(self, finance_client, mock_indices_data):
        """Contract: 返回 dict，key 为 sh/sz/cy，每个包含 name/close/change。"""
        with patch.object(
            finance_client._tencent, "get_index_data_async",
            return_value=mock_indices_data,
        ):
            result = await finance_client.get_index_data()

        assert isinstance(result, dict)
        for key in ("sh", "sz", "cy"):
            assert key in result
            index = result[key]
            assert "name" in index
            assert "close" in index
            assert "change" in index
            assert isinstance(index["name"], str)
            assert isinstance(index["close"], (int, float))
            assert isinstance(index["change"], (int, float))

    @pytest.mark.asyncio
    async def test_empty_returns_empty_dict(self, finance_client):
        """Contract: 所有数据源返回空时返回 {}。"""
        with patch.object(
            finance_client._tencent, "get_index_data_async", return_value={}
        ):
            with patch("akshare.stock_zh_index_spot_em", side_effect=Exception("fail")):
                result = await finance_client.get_index_data()

        assert result == {}

    @pytest.mark.asyncio
    async def test_fallback_to_akshare(self, finance_client, mock_indices_data):
        """Contract: 腾讯失败时降级到 akshare。"""
        import pandas as pd

        mock_df = pd.DataFrame({
            "名称": ["上证指数", "深证成指", "创业板指"],
            "最新价": [3881.28, 13536.56, 3251.55],
            "涨跌幅": [1.78, 1.43, 0.50],
        })

        with patch.object(
            finance_client._tencent, "get_index_data_async", return_value={}
        ):
            with patch("akshare.stock_zh_index_spot_em", return_value=mock_df):
                result = await finance_client.get_index_data()

        assert "sh" in result
        assert "sz" in result
        assert "cy" in result


# ── 成交额数据 contract ─────────────────────────────────────────


class TestVolumeDataContract:
    """成交额数据契约测试。"""

    @pytest.mark.asyncio
    async def test_normal_returns_dict_with_keys(self, finance_client, mock_stock_snapshot):
        """Contract: 返回 dict，包含 sh_volume/sz_volume/total_volume (float)。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
                {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
            ),
        ):
            result = await finance_client.get_volume_data()

        assert isinstance(result, dict)
        assert "sh_volume" in result
        assert "sz_volume" in result
        assert "total_volume" in result
        assert isinstance(result["sh_volume"], (int, float))
        assert isinstance(result["sz_volume"], (int, float))
        assert isinstance(result["total_volume"], (int, float))

    @pytest.mark.asyncio
    async def test_empty_snapshot_returns_zero(self, finance_client):
        """Contract: 快照为空时返回零值。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
                {"status": "error", "source": "official_exchange_turnover", "actual_count": 0, "expected_count": 2},
            ),
        ):
            result = await finance_client.get_volume_data()

        assert result == {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_zero(self, finance_client):
        """Contract: 所有数据源失败时返回零值。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            side_effect=Exception("fail"),
        ):
            result = await finance_client.get_volume_data()

        assert result == {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    def test_compute_volume_data_ignores_invalid_items(self, finance_client):
        """Contract: 非字典项不应导致成交额计算抛错。"""
        result = finance_client.compute_volume_data([
            "bad-item",
            {"f12": "600000", "f6": 100000000},
            {"f12": "000001", "f6": "250000000"},
            None,
        ])

        assert result == {"sh_volume": 1.0, "sz_volume": 2.5, "total_volume": 3.5}


# ── 涨跌统计 contract ─────────────────────────────────────────


class TestStatisticsContract:
    """涨跌统计数据契约测试。"""

    @pytest.mark.asyncio
    async def test_normal_returns_dict_with_keys(self, finance_client, mock_stock_snapshot):
        """Contract: 返回 dict，包含 up_count/down_count/flat_count (int)。"""
        with patch.object(
            finance_client, "_get_statistics_with_quality",
            return_value=(
                {"up_count": 2500, "down_count": 1800, "flat_count": 200},
                {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
            ),
        ):
            result = await finance_client.get_statistics()

        assert isinstance(result, dict)
        assert "up_count" in result
        assert "down_count" in result
        assert "flat_count" in result
        assert isinstance(result["up_count"], int)
        assert isinstance(result["down_count"], int)
        assert isinstance(result["flat_count"], int)

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_zero(self, finance_client):
        """Contract: 所有数据源失败时返回零值。"""
        with patch.object(
            finance_client, "_get_statistics_with_quality",
            side_effect=Exception("fail"),
        ):
            result = await finance_client.get_statistics()

        assert result == {"up_count": 0, "down_count": 0, "flat_count": 0}

    def test_compute_statistics_ignores_invalid_items(self, finance_client):
        """Contract: 非字典项不应导致涨跌统计抛错。"""
        result = finance_client.compute_statistics([
            "bad-item",
            {"f3": 1.23},
            {"f3": "-0.56"},
            {"f3": 0},
            None,
        ])

        assert result == {"up_count": 1, "down_count": 1, "flat_count": 1}


class TestEastMoneyCurlParsing:
    """东方财富 curl 响应解析测试。"""

    def test_parse_response_text_rejects_string_payload(self):
        """Contract: 根响应为字符串时不应被当成有效对象。"""
        client = EastMoneyCurlClient()
        assert client._parse_response_text('"unexpected"') == "unexpected"

    @pytest.mark.asyncio
    async def test_fetch_stock_snapshot_rejects_string_diff(self, finance_client):
        """Contract: diff 为字符串时应返回空快照。"""
        with patch.object(
            finance_client._eastmoney,
            "get_stock_list",
            return_value={"data": {"diff": "unexpected"}},
        ):
            result = await finance_client._fetch_stock_snapshot()

        stocks, quality = result
        assert stocks == []


class TestOfficialAndPytdxHelpers:
    """官方成交额与 pytdx 聚合辅助测试。"""

    def test_extract_sse_stock_turnover(self, finance_client):
        payload = {
            "result": [
                {"PRODUCT_CODE": "01", "TRADE_AMT": "100.00", "TRADE_DATE": "20260330"},
                {"PRODUCT_CODE": "17", "TRADE_AMT": "8409.45", "TRADE_DATE": "20260330"},
            ]
        }
        turnover, trade_date = finance_client._extract_sse_stock_turnover(payload)
        assert turnover == pytest.approx(8409.45)
        assert trade_date == "20260330"

    def test_extract_szse_stock_turnover(self, finance_client):
        payload = [
            {
                "metadata": {
                    "conditions": [
                        {"name": "txtQueryDate", "defaultValue": "2026-03-30"},
                    ]
                },
                "data": [
                    {"zbmc": "成交量（亿）", "gp": "653.79"},
                    {"zbmc": "成交金额（亿元）", "gp": "10,762.98"},
                ],
            }
        ]
        turnover, trade_date = finance_client._extract_szse_stock_turnover(payload)
        assert turnover == pytest.approx(10762.98)
        assert trade_date == "20260330"

    def test_compute_statistics_from_pytdx_quotes(self, finance_client):
        rows = [
            {"price": 10.0, "last_close": 9.5},
            {"price": 8.0, "last_close": 8.2},
            {"price": 5.0, "last_close": 5.0},
            {"price": None, "last_close": 5.0},
        ]
        statistics, actual_count = finance_client._compute_statistics_from_pytdx_quotes(rows)
        assert statistics == {"up_count": 1, "down_count": 1, "flat_count": 1}
        assert actual_count == 3


# ── 板块数据 contract ─────────────────────────────────────────


class TestSectorsContract:
    """板块数据契约测试。"""

    @pytest.mark.asyncio
    async def test_primary_sector_adapter_is_preferred(self, finance_client):
        """Contract: 板块优先走专用 primary adapter。"""
        primary_result = {
            "top_sectors": [{"name": "半导体", "code": "BK001", "change": 0.035}],
            "bottom_sectors": [{"name": "白酒", "code": "BK002", "change": -0.025}],
        }
        with patch.object(
            finance_client,
            "_get_sector_data_from_stock_sector_spot",
            new_callable=AsyncMock,
            return_value=primary_result,
        ) as mock_primary:
            with patch.object(
                finance_client,
                "_get_sector_data_from_board_name_em",
                new_callable=AsyncMock,
            ) as mock_backup:
                with patch.object(
                    finance_client,
                    "_get_sector_data_from_eastmoney",
                    new_callable=AsyncMock,
                ) as mock_curl:
                    result = await finance_client.get_sector_data()

        assert result == primary_result
        mock_primary.assert_awaited_once()
        mock_backup.assert_not_called()
        mock_curl.assert_not_called()

    @pytest.mark.asyncio
    async def test_sector_falls_back_in_declared_order(self, finance_client):
        """Contract: primary 失败时按声明顺序降级。"""
        backup_result = {
            "top_sectors": [{"name": "AI", "code": "", "change": 0.041}],
            "bottom_sectors": [{"name": "地产", "code": "", "change": -0.031}],
        }
        with patch.object(
            finance_client,
            "_get_sector_data_from_stock_sector_spot",
            new_callable=AsyncMock,
            side_effect=Exception("primary fail"),
        ) as mock_primary:
            with patch.object(
                finance_client,
                "_get_sector_data_from_board_name_em",
                new_callable=AsyncMock,
                return_value=backup_result,
            ) as mock_backup:
                with patch.object(
                    finance_client,
                    "_get_sector_data_from_eastmoney",
                    new_callable=AsyncMock,
                ) as mock_curl:
                    result = await finance_client.get_sector_data()

        assert result == backup_result
        mock_primary.assert_awaited_once()
        mock_backup.assert_awaited_once()
        mock_curl.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_returns_dict_with_keys(self, finance_client):
        """Contract: 返回 dict，包含 top_sectors/bottom_sectors (list)。"""
        mock_data = {
            "data": {
                "diff": [
                    {"f14": "半导体", "f3": 3.5},
                    {"f14": "光伏", "f3": 2.8},
                    {"f14": "白酒", "f3": -2.5},
                    {"f14": "医药", "f3": -1.8},
                    {"f14": "新能源", "f3": 1.2},
                ]
            }
        }
        with patch.object(
            finance_client._eastmoney, "get_board_list", return_value=mock_data
        ):
            result = await finance_client.get_sector_data()

        assert isinstance(result, dict)
        assert "top_sectors" in result
        assert "bottom_sectors" in result
        assert isinstance(result["top_sectors"], list)
        assert isinstance(result["bottom_sectors"], list)
        for sector in result["top_sectors"]:
            assert "name" in sector
            assert "change" in sector

    @pytest.mark.asyncio
    async def test_empty_returns_empty_structure(self, finance_client):
        """Contract: 无数据时返回 {top_sectors: [], bottom_sectors: []}。"""
        with patch.object(
            finance_client,
            "_get_sector_data_from_stock_sector_spot",
            new_callable=AsyncMock,
            side_effect=Exception("primary fail"),
        ):
            with patch.object(
                finance_client._eastmoney, "get_board_list", return_value=None
            ):
                with patch(
                    "akshare.stock_board_concept_name_em", side_effect=Exception("fail")
                ):
                    result = await finance_client.get_sector_data()

        assert result == {"top_sectors": [], "bottom_sectors": []}


# ── 涨停股 contract ─────────────────────────────────────────


class TestLimitUpContract:
    """涨停股数据契约测试。"""

    @pytest.mark.asyncio
    async def test_primary_limit_up_adapter_is_preferred(self, finance_client):
        """Contract: 涨停股优先走专用涨停池 adapter。"""
        expected = [{"name": "股票A", "code": "000001", "change": 0.1, "limit_days": 2}]
        with patch.object(
            finance_client,
            "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_primary:
            with patch.object(
                finance_client,
                "_get_limit_up_from_snapshot",
                new_callable=AsyncMock,
            ) as mock_snapshot:
                with patch.object(
                    finance_client,
                    "_get_limit_up_from_spot_em",
                    new_callable=AsyncMock,
                ) as mock_spot:
                    result = await finance_client.get_limit_up_stocks()

        assert result == expected
        mock_primary.assert_awaited_once()
        mock_snapshot.assert_not_called()
        mock_spot.assert_not_called()

    @pytest.mark.asyncio
    async def test_limit_up_primary_receives_trade_date(self, finance_client):
        """Contract: trade_date 透传给专用涨停池 adapter。"""
        from datetime import date

        trade_date = date(2026, 3, 27)
        with patch.object(
            finance_client,
            "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_primary:
            await finance_client.get_limit_up_stocks(trade_date=trade_date)

        assert mock_primary.await_args.kwargs["trade_date"] == trade_date

    @pytest.mark.asyncio
    async def test_limit_up_falls_back_to_snapshot(self, finance_client):
        """Contract: 专用涨停池失败时回退到快照 adapter。"""
        expected = [{"name": "股票B", "code": "000002", "change": 0.0999}]
        with patch.object(
            finance_client,
            "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock,
            side_effect=Exception("primary fail"),
        ) as mock_primary:
            with patch.object(
                finance_client,
                "_get_limit_up_from_snapshot",
                new_callable=AsyncMock,
                return_value=expected,
            ) as mock_snapshot:
                with patch.object(
                    finance_client,
                    "_get_limit_up_from_spot_em",
                    new_callable=AsyncMock,
                ) as mock_spot:
                    result = await finance_client.get_limit_up_stocks()

        assert result == expected
        mock_primary.assert_awaited_once()
        mock_snapshot.assert_awaited_once()
        mock_spot.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_returns_list(self, finance_client):
        """Contract: 返回 list，每个元素包含 name/code/change。"""
        mock_data = {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "股票A", "f3": 10.0},
                    {"f12": "000002", "f14": "股票B", "f3": 9.99},
                ]
            }
        }
        with patch.object(
            finance_client._eastmoney, "get_stock_list", return_value=mock_data
        ):
            result = await finance_client.get_limit_up_stocks()

        assert isinstance(result, list)
        for stock in result:
            assert "name" in stock
            assert "code" in stock
            assert "change" in stock

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, finance_client):
        """Contract: 无涨停股时返回 []。"""
        with patch.object(
            finance_client,
            "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock,
            side_effect=Exception("primary fail"),
        ):
            with patch.object(
                finance_client._eastmoney, "get_stock_list", return_value=None
            ):
                with patch("akshare.stock_zh_a_spot_em", side_effect=Exception("fail")):
                    result = await finance_client.get_limit_up_stocks()

        assert result == []


# ── compute_* 辅助方法 contract ────────────────────────────────


class TestComputeHelpers:
    """测试 compute_volume_data / compute_statistics 辅助方法。"""

    def test_compute_volume_data_with_data(self, finance_client, mock_stock_snapshot):
        """Contract: 正常数据返回正值成交额。"""
        result = finance_client.compute_volume_data(mock_stock_snapshot)
        assert result["sh_volume"] > 0
        assert result["sz_volume"] > 0
        assert result["total_volume"] == round(
            result["sh_volume"] + result["sz_volume"], 2
        )

    def test_compute_volume_data_empty(self, finance_client):
        """Contract: 空快照返回零值。"""
        result = finance_client.compute_volume_data([])
        assert result == {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    def test_compute_statistics_with_data(self, finance_client, mock_stock_snapshot):
        """Contract: 正常数据返回涨跌统计。"""
        result = finance_client.compute_statistics(mock_stock_snapshot)
        assert result["up_count"] > 0
        assert result["down_count"] > 0
        assert result["flat_count"] >= 0

    def test_compute_statistics_empty(self, finance_client):
        """Contract: 空快照返回零值。"""
        result = finance_client.compute_statistics([])
        assert result == {"up_count": 0, "down_count": 0, "flat_count": 0}


# ── 聚合数据 contract ─────────────────────────────────────────


class TestAllMarketDataContract:
    """聚合市场数据契约测试。"""

    @pytest.mark.asyncio
    async def test_normal_includes_all_keys(
        self, finance_client, mock_indices_data, mock_stock_snapshot
    ):
        """Contract: 返回 dict 包含 indices/volume/statistics/sectors/limit_up/fetch_time。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 8409.45, "sz_volume": 10762.98, "total_volume": 19172.43},
                {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 2500, "down_count": 1800, "flat_count": 200},
                    {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
                ),
            ):
                with patch.object(finance_client, "get_index_data", return_value=mock_indices_data):
                    with patch.object(
                        finance_client,
                        "get_sector_data",
                        return_value={"top_sectors": [], "bottom_sectors": []},
                    ):
                        with patch.object(finance_client, "_get_limit_up_with_quality", return_value=([], {"source_type": "none", "status": "error"})):
                            result = await finance_client.get_all_market_data()

        assert "indices" in result
        assert "volume" in result
        assert "statistics" in result
        assert "sectors" in result
        assert "limit_up" in result
        assert "fetch_time" in result
        assert "breadth_quality" in result
        assert "limit_up_quality" in result

    @pytest.mark.asyncio
    async def test_partial_failure_preserves_structure(
        self, finance_client, mock_indices_data, mock_volume_data
    ):
        """Contract: 部分数据源异常时整体结构不变，失败部分返回降级值。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 8409.45, "sz_volume": 10762.98, "total_volume": 19172.43},
                {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 2500, "down_count": 1800, "flat_count": 200},
                    {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
                ),
            ):
                with patch.object(finance_client, "get_index_data", return_value=mock_indices_data):
                    with patch.object(
                        finance_client, "get_sector_data", side_effect=Exception("Sector error")
                    ):
                        with patch.object(
                            finance_client, "_get_limit_up_with_quality",
                            return_value=([], {"source_type": "none", "status": "error"}),
                        ):
                            result = await finance_client.get_all_market_data()

        assert result["indices"] == mock_indices_data
        assert result["volume"]["total_volume"] > 0
        assert result["statistics"]["up_count"] + result["statistics"]["down_count"] > 0
        assert result["sectors"] == {}
        assert result["limit_up"] == []

    @pytest.mark.asyncio
    async def test_get_all_market_data_passes_trade_date_to_limit_up(self, finance_client):
        """Contract: 聚合取数应将 trade_date 传给涨停池 adapter。"""
        from datetime import date

        trade_date = date(2026, 3, 27)
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 1.0, "sz_volume": 2.0, "total_volume": 3.0},
                {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 1, "down_count": 1, "flat_count": 0},
                    {"status": "ok", "source": "pytdx_quotes", "actual_count": 2, "expected_count": 2},
                ),
            ):
                with patch.object(finance_client, "get_index_data", return_value={}):
                    with patch.object(finance_client, "get_sector_data", return_value={"top_sectors": [], "bottom_sectors": []}):
                        with patch.object(
                            finance_client,
                            "_get_limit_up_with_quality",
                            new_callable=AsyncMock,
                            return_value=([], {"source_type": "none", "status": "error"}),
                        ) as mock_limit:
                            await finance_client.get_all_market_data(trade_date=trade_date)

        assert mock_limit.await_args.kwargs["trade_date"] == trade_date

    @pytest.mark.asyncio
    async def test_all_failure_returns_degraded_structure(self, finance_client):
        """Contract: 所有数据源异常时返回正确的降级结构。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
                {"status": "error", "source": "official_exchange_turnover", "actual_count": 0, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 0, "down_count": 0, "flat_count": 0},
                    {"status": "error", "source": "pytdx_quotes", "actual_count": 0, "expected_count": 5518},
                ),
            ):
                with patch.object(finance_client, "get_index_data", side_effect=Exception("Error")):
                    with patch.object(finance_client, "get_sector_data", side_effect=Exception("Error")):
                        with patch.object(finance_client, "_get_limit_up_with_quality", side_effect=Exception("Error")):
                            result = await finance_client.get_all_market_data()

        assert isinstance(result["indices"], dict)
        assert isinstance(result["volume"], dict)
        assert isinstance(result["statistics"], dict)
        assert isinstance(result["sectors"], dict)
        assert isinstance(result["limit_up"], list)


# ── 网络禁用 contract ─────────────────────────────────────────


class TestDisabledNetworkContract:
    """网络禁用时返回正确的空值 contract。"""

    @pytest.mark.asyncio
    async def test_disabled_network_returns_empty_contracts(self, finance_client):
        """Contract: 网络禁用时所有方法返回正确的空值结构。"""
        from src.api import finance

        finance._DISABLE_NETWORK = True
        try:
            result = await finance_client.get_all_market_data()

            assert result["indices"] == {}
            assert result["volume"] == {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}
            assert result["statistics"] == {
                "up_count": 0,
                "down_count": 0,
                "flat_count": 0,
            }
            assert result["sectors"] == {"top_sectors": [], "bottom_sectors": []}
            assert result["limit_up"] == []
        finally:
            finance._DISABLE_NETWORK = False


# ── 宽度数据质量 contract ─────────────────────────────────────────


class TestBreadthQualityContract:
    """宽度数据（成交额/涨跌统计）质量状态契约测试。"""

    def test_normalize_snapshot_handles_dict_diff(self, finance_client):
        """Contract: data.diff 为 dict 时应正确提取股票列表。"""
        data = {
            "data": {
                "total": 3,
                "diff": {
                    "0": {"f12": "600000", "f14": "浦发银行", "f3": 1.83, "f6": 611456194.0},
                    "1": {"f12": "000001", "f14": "平安银行", "f3": -0.56, "f6": 823456789.0},
                    "2": {"f12": "300001", "f14": "特锐德", "f3": 0.0, "f6": 123456789.0},
                },
            }
        }
        result = finance_client._normalize_stock_snapshot(data)
        assert len(result) == 3
        assert result[0]["f12"] == "600000"

    def test_normalize_snapshot_handles_list_diff(self, finance_client):
        """Contract: data.diff 为 list 时应保持向后兼容。"""
        data = {
            "data": {
                "total": 2,
                "diff": [
                    {"f12": "600000", "f14": "浦发银行", "f3": 1.83, "f6": 611456194.0},
                    {"f12": "000001", "f14": "平安银行", "f3": -0.56, "f6": 823456789.0},
                ],
            }
        }
        result = finance_client._normalize_stock_snapshot(data)
        assert len(result) == 2

    def test_normalize_snapshot_empty_diff(self, finance_client):
        """Contract: diff 为空时返回空列表。"""
        assert finance_client._normalize_stock_snapshot({"data": {"diff": []}}) == []
        assert finance_client._normalize_stock_snapshot({"data": {"diff": {}}}) == []
        assert finance_client._normalize_stock_snapshot({"data": {}}) == []
        assert finance_client._normalize_stock_snapshot({}) == []

    @pytest.mark.asyncio
    async def test_fetch_snapshot_returns_quality_ok(self, finance_client):
        """Contract: 完整快照返回 status=ok。"""
        mock_stocks = [
            {"f12": "600000", "f3": 1.83, "f6": 100},
        ]
        with patch.object(
            finance_client._eastmoney,
            "get_stock_list",
            return_value={"data": {"total": 1, "diff": [mock_stocks[0]]}},
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "ok"
        assert quality["actual_count"] == 1
        assert quality["expected_count"] == 1
        assert len(stocks) == 1

    @pytest.mark.asyncio
    async def test_fetch_snapshot_returns_quality_partial(self, finance_client):
        """Contract: 不完整快照返回 status=partial。"""
        stock = {"f12": "600000", "f3": 1.83, "f6": 100}
        # First page returns total=10 but only 1 stock
        first_page = {"data": {"total": 10, "diff": [stock]}}
        # Subsequent pages return None (failure) — 需要 >=2 次连续空页才终止
        with patch.object(
            finance_client._eastmoney, "get_stock_list",
            side_effect=[first_page, None, None],
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "partial"
        assert quality["actual_count"] == 1
        assert quality["expected_count"] == 10

    @pytest.mark.asyncio
    async def test_fetch_snapshot_returns_quality_error(self, finance_client):
        """Contract: 完全失败返回 status=error。"""
        with patch.object(
            finance_client._eastmoney, "get_stock_list", return_value=None
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "error"
        assert stocks == []

    @pytest.mark.asyncio
    async def test_fetch_snapshot_paginates(self, finance_client):
        """Contract: 分页聚合应累积所有页的记录。"""
        page1_data = {"data": {"total": 3, "diff": [
            {"f12": "600000", "f3": 1.0, "f6": 100},
        ]}}
        page2_data = {"data": {"diff": [
            {"f12": "000001", "f3": -1.0, "f6": 200},
            {"f12": "300001", "f3": 0.0, "f6": 300},
        ]}}
        with patch.object(
            finance_client._eastmoney, "get_stock_list",
            side_effect=[page1_data, page2_data],
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "ok"
        assert len(stocks) == 3
        assert quality["actual_count"] == 3

    @pytest.mark.asyncio
    async def test_get_volume_with_quality_prefers_official_sources(self, finance_client):
        with patch.object(
            finance_client, "_fetch_sse_official_turnover",
            new_callable=AsyncMock,
            return_value=(8409.45, "20260330"),
        ):
            with patch.object(
                finance_client, "_fetch_szse_official_turnover",
                new_callable=AsyncMock,
                return_value=(10762.98, "20260330"),
            ):
                volume, quality = await finance_client._get_volume_with_quality(date(2026, 3, 30))

        assert volume["total_volume"] == pytest.approx(19172.43)
        assert quality["status"] == "ok"
        assert quality["source"] == "official_exchange_turnover"

    @pytest.mark.asyncio
    async def test_get_volume_with_quality_falls_back_to_akshare(self, finance_client):
        with patch.object(
            finance_client, "_fetch_sse_official_turnover",
            new_callable=AsyncMock,
            side_effect=Exception("sse fail"),
        ):
            with patch.object(
                finance_client, "_fetch_szse_official_turnover",
                new_callable=AsyncMock,
                side_effect=Exception("szse fail"),
            ):
                with patch.object(
                    finance_client, "_get_volume_data_from_spot_em",
                    new_callable=AsyncMock,
                    return_value={"sh_volume": 1.0, "sz_volume": 2.0, "total_volume": 3.0},
                ):
                    volume, quality = await finance_client._get_volume_with_quality(date(2026, 3, 30))

        assert volume["total_volume"] == 3.0
        assert quality["status"] == "ok"
        assert quality["source"] == "akshare_spot_em"

    @pytest.mark.asyncio
    async def test_get_statistics_with_quality_prefers_pytdx(self, finance_client):
        with patch.object(
            finance_client, "_fetch_pytdx_statistics",
            new_callable=AsyncMock,
            return_value=(
                {"up_count": 1, "down_count": 1, "flat_count": 0},
                {"status": "ok", "source": "pytdx_quotes", "actual_count": 2, "expected_count": 2},
            ),
        ):
            statistics, quality = await finance_client._get_statistics_with_quality()

        assert statistics["up_count"] == 1
        assert quality["source"] == "pytdx_quotes"

    @pytest.mark.asyncio
    async def test_get_statistics_with_quality_returns_partial_when_fallback_fails(self, finance_client):
        with patch.object(
            finance_client, "_fetch_pytdx_statistics",
            new_callable=AsyncMock,
            return_value=(
                {"up_count": 1, "down_count": 1, "flat_count": 0},
                {"status": "partial", "source": "pytdx_quotes", "actual_count": 100, "expected_count": 5518},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_from_spot_em",
                new_callable=AsyncMock,
                side_effect=Exception("fail"),
            ):
                statistics, quality = await finance_client._get_statistics_with_quality()

        assert statistics == {"up_count": 1, "down_count": 1, "flat_count": 0}
        assert quality["status"] == "partial"

    @pytest.mark.asyncio
    async def test_get_all_market_data_includes_breadth_quality(
        self, finance_client, mock_stock_snapshot, mock_indices_data
    ):
        """Contract: get_all_market_data 返回 breadth_quality 字段。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 8409.45, "sz_volume": 10762.98, "total_volume": 19172.43},
                {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 2500, "down_count": 1800, "flat_count": 200},
                    {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
                ),
            ):
                with patch.object(finance_client, "get_index_data", return_value=mock_indices_data):
                    with patch.object(finance_client, "get_sector_data", return_value={"top_sectors": [], "bottom_sectors": []}):
                        with patch.object(finance_client, "_get_limit_up_with_quality", return_value=([], {"source_type": "dedicated_pool", "status": "ok"})):
                            result = await finance_client.get_all_market_data()

        assert "breadth_quality" in result
        assert "volume" in result["breadth_quality"]
        assert "statistics" in result["breadth_quality"]
        assert result["breadth_quality"]["volume"]["status"] == "ok"
        assert result["breadth_quality"]["statistics"]["status"] == "ok"
        assert result["breadth_quality"]["volume"]["source"] == "official_exchange_turnover"
        assert "limit_up_quality" in result
        assert result["limit_up_quality"]["source_type"] == "dedicated_pool"

    @pytest.mark.asyncio
    async def test_get_all_market_data_breadth_error_when_primary_and_fallback_fail(self, finance_client):
        """Contract: 主路径与兜底链路都失败时 breadth_quality 为 error。"""
        with patch.object(
            finance_client, "_get_volume_with_quality",
            return_value=(
                {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
                {"status": "error", "source": "official_exchange_turnover", "actual_count": 0, "expected_count": 2},
            ),
        ):
            with patch.object(
                finance_client, "_get_statistics_with_quality",
                return_value=(
                    {"up_count": 0, "down_count": 0, "flat_count": 0},
                    {"status": "error", "source": "pytdx_quotes", "actual_count": 0, "expected_count": 5518},
                ),
            ):
                with patch.object(finance_client, "get_index_data", return_value={}):
                    with patch.object(finance_client, "get_sector_data", return_value={"top_sectors": [], "bottom_sectors": []}):
                        with patch.object(finance_client, "_get_limit_up_with_quality", return_value=([], {"source_type": "none", "status": "error"})):
                            result = await finance_client.get_all_market_data()

        assert result["breadth_quality"]["volume"]["status"] == "error"
        assert result["breadth_quality"]["statistics"]["status"] == "error"


# ── 四态质量模型测试 ─────────────────────────────────────────


class TestStatisticsQualityModel:
    """涨跌统计四态质量模型测试。"""

    def test_ok_when_actual_equals_expected(self, finance_client):
        assert finance_client._determine_statistics_quality(5000, 5000) == "ok"

    def test_ok_when_actual_exceeds_expected(self, finance_client):
        assert finance_client._determine_statistics_quality(5001, 5000) == "ok"

    def test_error_when_expected_zero(self, finance_client):
        assert finance_client._determine_statistics_quality(0, 0) == "error"

    def test_error_when_actual_zero(self, finance_client):
        assert finance_client._determine_statistics_quality(0, 5000) == "error"

    def test_near_complete_when_gap_within_abs_threshold(self, finance_client):
        # gap = 30 < 50 (abs threshold)
        assert finance_client._determine_statistics_quality(4970, 5000) == "near-complete"

    def test_near_complete_when_gap_within_pct_threshold(self, finance_client):
        # gap = 45, threshold = max(50, int(10000 * 0.01)) = max(50, 100) = 100
        assert finance_client._determine_statistics_quality(9955, 10000) == "near-complete"

    def test_partial_when_gap_exceeds_threshold(self, finance_client):
        # gap = 200, threshold = max(50, int(5000 * 0.01)) = 50
        assert finance_client._determine_statistics_quality(4800, 5000) == "partial"


class TestLimitUpQualityContract:
    """涨停股来源质量标记契约测试。"""

    @pytest.mark.asyncio
    async def test_zt_pool_returns_dedicated_pool(self, finance_client):
        """Contract: 专用涨停池返回 dedicated_pool 来源。"""
        with patch.object(
            finance_client, "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock, return_value=[{"name": "A", "code": "001", "change": 0.1}],
        ):
            stocks, quality = await finance_client._get_limit_up_with_quality()

        assert quality["source_type"] == "dedicated_pool"
        assert quality["status"] == "ok"
        assert len(stocks) == 1

    @pytest.mark.asyncio
    async def test_snapshot_fallback_returns_approximate(self, finance_client):
        """Contract: 快照兜底返回 approximate_candidates 来源。"""
        with patch.object(
            finance_client, "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock, side_effect=Exception("fail"),
        ):
            with patch.object(
                finance_client, "_get_limit_up_from_snapshot",
                new_callable=AsyncMock, return_value=[{"name": "B", "code": "002", "change": 0.099}],
            ):
                stocks, quality = await finance_client._get_limit_up_with_quality()

        assert quality["source_type"] == "approximate_candidates"
        assert quality["status"] == "ok"

    @pytest.mark.asyncio
    async def test_all_fail_returns_none(self, finance_client):
        """Contract: 全部失败返回 none 来源。"""
        with patch.object(
            finance_client, "_get_limit_up_from_zt_pool",
            new_callable=AsyncMock, side_effect=Exception("fail"),
        ):
            with patch.object(
                finance_client, "_get_limit_up_from_snapshot",
                new_callable=AsyncMock, side_effect=Exception("fail"),
            ):
                with patch.object(
                    finance_client, "_get_limit_up_from_spot_em",
                    new_callable=AsyncMock, side_effect=Exception("fail"),
                ):
                    stocks, quality = await finance_client._get_limit_up_with_quality()

        assert quality["source_type"] == "none"
        assert quality["status"] == "error"
        assert stocks == []

    @pytest.mark.asyncio
    async def test_get_statistics_with_quality_returns_near_complete(self, finance_client):
        """Contract: near-complete 统计应返回实际值而非零值。"""
        with patch.object(
            finance_client, "_fetch_pytdx_statistics",
            new_callable=AsyncMock,
            return_value=(
                {"up_count": 5200, "down_count": 0, "flat_count": 0},
                {"status": "near-complete", "source": "pytdx_quotes", "actual_count": 5200, "expected_count": 5201},
            ),
        ):
            statistics, quality = await finance_client._get_statistics_with_quality()

        assert statistics["up_count"] == 5200
        assert quality["status"] == "near-complete"


# ── 分页回归测试 (Task 3.1-3.3) ──────────────────────────────


class TestSnapshotPaginationRegression:
    """分页回归测试：上游忽略 pz=5000、每页仅返回 100 条、需要超过 20 页的场景。"""

    @staticmethod
    def _make_page(page_num: int, total: int, page_size: int = 100) -> dict:
        """生成模拟的东方财富分页响应。"""
        start = (page_num - 1) * page_size
        end = min(start + page_size, total)
        diff = {
            str(i): {"f12": f"{600000 + i:06d}", "f14": f"股票{i}", "f3": 1.0, "f6": 100000.0}
            for i in range(start, end)
        }
        return {"data": {"total": total, "diff": diff}}

    @pytest.mark.asyncio
    async def test_pagination_beyond_20_pages_when_upstream_ignores_pz(self, finance_client):
        """Regression: 上游忽略 pz=5000 每页仅返回 100 条时，应能抓完 5518 条。

        5518 / 100 = 56 页，远超旧版固定 20 页上限。
        """
        total = 5518
        page_size = 100
        num_pages = 56  # math.ceil(5518 / 100)

        pages = [self._make_page(p, total, page_size) for p in range(1, num_pages + 1)]
        # 最后一页之后返回空
        pages.append(None)

        with patch.object(
            finance_client._eastmoney, "get_stock_list", side_effect=pages
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "ok"
        assert quality["actual_count"] == total
        assert quality["expected_count"] == total
        assert len(stocks) == total

    @pytest.mark.asyncio
    async def test_pagination_deduplicates_by_stock_code(self, finance_client):
        """Regression: 页间重复股票代码应被去重，完整性基于唯一数。"""
        # 首页返回 3 只股票，其中 600001 在第二页重复
        page1 = {"data": {"total": 4, "diff": {
            "0": {"f12": "600000", "f14": "股票A", "f3": 1.0, "f6": 100},
            "1": {"f12": "600001", "f14": "股票B", "f3": 2.0, "f6": 200},
            "2": {"f12": "600002", "f14": "股票C", "f3": 3.0, "f6": 300},
        }}}
        page2 = {"data": {"diff": {
            "0": {"f12": "600001", "f14": "股票B重复", "f3": 2.5, "f6": 250},
            "1": {"f12": "600003", "f14": "股票D", "f3": 4.0, "f6": 400},
        }}}

        with patch.object(
            finance_client._eastmoney, "get_stock_list", side_effect=[page1, page2]
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        codes = {s["f12"] for s in stocks}
        assert len(codes) == 4  # 600000, 600001, 600002, 600003
        assert quality["status"] == "ok"
        assert quality["actual_count"] == 4

    @pytest.mark.asyncio
    async def test_pagination_stops_when_no_new_records(self, finance_client):
        """Regression: 后续页无新增记录时应短路退出，不再继续请求。"""
        page1 = {"data": {"total": 100, "diff": {
            str(i): {"f12": f"{600000 + i:06d}", "f14": f"股票{i}", "f3": 1.0, "f6": 100}
            for i in range(10)
        }}}
        # 第二页全部是重复代码
        page2 = {"data": {"diff": {
            "0": {"f12": "600000", "f14": "股票0", "f3": 1.0, "f6": 100},
            "1": {"f12": "600001", "f14": "股票1", "f3": 1.0, "f6": 100},
        }}}
        # 不应请求第三页
        extra_page = {"data": {"total": 100, "diff": {
            "0": {"f12": "999999", "f14": "不应出现", "f3": 1.0, "f6": 100},
        }}}

        with patch.object(
            finance_client._eastmoney, "get_stock_list", side_effect=[page1, page2, extra_page]
        ) as mock_list:
            stocks, quality = await finance_client._fetch_stock_snapshot()

        # 应只调用 2 次（首页 + 第二页），第三页不被请求
        assert mock_list.call_count == 2
        assert quality["status"] == "partial"
        assert quality["actual_count"] == 10

    @pytest.mark.asyncio
    async def test_pagination_stops_on_consecutive_empty_pages(self, finance_client):
        """Regression: 连续空页应终止分页。"""
        page1 = {"data": {"total": 500, "diff": {
            str(i): {"f12": f"{600000 + i:06d}", "f14": f"股票{i}", "f3": 1.0, "f6": 100}
            for i in range(10)
        }}}
        # 后续页连续返回 None
        with patch.object(
            finance_client._eastmoney, "get_stock_list",
            side_effect=[page1, None, None],
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "partial"
        assert quality["actual_count"] == 10

    @pytest.mark.asyncio
    async def test_full_pagination_feeds_market_summary_ok_path(self, finance_client):
        """Regression: 完整分页成功时 market-summary 不应落入 partial 路径。

        模拟 get_all_market_data 流程，验证成交额和涨跌统计从完整快照正确计算。
        """
        total = 300
        page_size = 100
        all_stocks = []
        for i in range(total):
            all_stocks.append({
                "f12": f"{600000 + i:06d}",
                "f14": f"股票{i}",
                "f3": 1.0 if i % 3 == 0 else (-1.0 if i % 3 == 1 else 0.0),
                "f6": 1000000.0,
            })

        # 分三页
        pages = []
        for p in range(3):
            chunk = all_stocks[p * 100:(p + 1) * 100]
            diff = {str(i): s for i, s in enumerate(chunk)}
            pages.append({"data": {"total": total, "diff": diff}})
        pages.append(None)  # 终止

        with patch.object(
            finance_client._eastmoney, "get_stock_list", side_effect=pages
        ):
            stocks, quality = await finance_client._fetch_stock_snapshot()

        assert quality["status"] == "ok"
        assert quality["actual_count"] == total

        # 验证成交额和涨跌统计可从完整快照正确计算
        volume = finance_client.compute_volume_data(stocks)
        assert volume["total_volume"] > 0

        stats = finance_client.compute_statistics(stocks)
        assert stats["up_count"] > 0
        assert stats["down_count"] > 0
        assert stats["flat_count"] >= 0


# ── 共享备用快照回归测试 ──────────────────────────────────────


class TestLegacyFallbackRegression:
    """回归测试：成交额和涨跌统计分别回退到旧链路。"""

    @pytest.mark.asyncio
    async def test_volume_fallback_uses_akshare(self, finance_client):
        with patch.object(
            finance_client, "_fetch_sse_official_turnover",
            new_callable=AsyncMock,
            side_effect=Exception("sse fail"),
        ):
            with patch.object(
                finance_client, "_fetch_szse_official_turnover",
                new_callable=AsyncMock,
                side_effect=Exception("szse fail"),
            ):
                with patch.object(
                    finance_client, "_get_volume_data_from_spot_em",
                    new_callable=AsyncMock,
                    return_value={"sh_volume": 10.0, "sz_volume": 5.0, "total_volume": 15.0},
                ):
                    volume, quality = await finance_client._get_volume_with_quality(date(2026, 3, 30))

        assert volume["total_volume"] == 15.0
        assert quality["source"] == "akshare_spot_em"

    @pytest.mark.asyncio
    async def test_statistics_fallback_uses_akshare(self, finance_client):
        with patch.object(
            finance_client, "_fetch_pytdx_statistics",
            new_callable=AsyncMock,
            return_value=(
                {"up_count": 1, "down_count": 1, "flat_count": 0},
                {"status": "partial", "source": "pytdx_quotes", "actual_count": 100, "expected_count": 5518},
            ),
        ), patch.object(
            finance_client, "_get_statistics_from_spot_em",
            new_callable=AsyncMock,
            return_value={"up_count": 2, "down_count": 1, "flat_count": 0},
        ) as mock_fallback:
            statistics, quality = await finance_client._get_statistics_with_quality()

        assert statistics == {"up_count": 1, "down_count": 1, "flat_count": 0}
        assert quality["source"] == "pytdx_quotes"
        assert quality["status"] == "partial"
        mock_fallback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_statistics_fallback_failure_returns_zeros(self, finance_client):
        """Regression: pytdx error 时直接返回零值，不再尝试旧链路。"""
        with patch.object(
            finance_client, "_fetch_pytdx_statistics",
            new_callable=AsyncMock,
            return_value=(
                {"up_count": 1, "down_count": 1, "flat_count": 0},
                {"status": "error", "source": "pytdx_quotes", "actual_count": 0, "expected_count": 5518},
            ),
        ), patch.object(
            finance_client, "_get_statistics_from_spot_em",
            new_callable=AsyncMock,
            side_effect=Exception("akshare fail"),
        ) as mock_fallback:
            statistics, quality = await finance_client._get_statistics_with_quality()

        assert statistics == {"up_count": 0, "down_count": 0, "flat_count": 0}
        assert quality["status"] == "error"
        mock_fallback.assert_not_awaited()
