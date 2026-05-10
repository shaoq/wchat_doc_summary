"""可恢复市场数据失败日志语义测试。

验证：
- pytdx 单个 host 失败不产生默认 warning，全部失败时只产生最终 warning
- 海外市场主源失败后 fallback 成功时不产生默认 warning
- 海外市场所有 provider 失败时只产生最终 warning
"""

import logging
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from src.api.finance import FinanceClient


def _mock_pytdx_api():
    """创建模拟成功连接的 pytdx API 实例。"""
    from contextlib import contextmanager

    class MockAPI:
        @contextmanager
        def connect(self, host, port, time_out=5):
            yield self

        def get_security_count(self, market):
            return 2

        def get_security_list(self, market, start):
            return [{"code": "000001"}, {"code": "000002"}]

        def get_security_quotes(self, batch):
            return [
                {"code": "000001", "price": 10.0, "last_close": 9.5},
                {"code": "000002", "price": 8.0, "last_close": 8.0},
            ]

    return MockAPI()


@pytest.fixture
def finance_client():
    return FinanceClient()


# ---------------------------------------------------------------------------
# 海外市场日志测试
# ---------------------------------------------------------------------------


class TestOverseasMarketLogging:
    """海外市场上下文 provider chain 日志级别测试。"""

    @pytest.mark.asyncio
    async def test_primary_401_fallback_success_no_warning(self, finance_client, caplog):
        """主源 401 且 fallback 成功时不应产生 warning 级别日志。"""
        mock_rows = [
            {"symbol": "^DJI", "regularMarketPrice": 39000.0, "regularMarketChangePercent": 0.4, "regularMarketTime": 1710500000},
            {"symbol": "^GSPC", "regularMarketPrice": 5200.0, "regularMarketChangePercent": 0.6, "regularMarketTime": 1710500000},
            {"symbol": "^IXIC", "regularMarketPrice": 16500.0, "regularMarketChangePercent": 0.9, "regularMarketTime": 1710500000},
            {"symbol": "^VIX", "regularMarketPrice": 13.5, "regularMarketChangePercent": -2.0, "regularMarketTime": 1710500000},
            {"symbol": "DX-Y.NYB", "regularMarketPrice": 104.1, "regularMarketChangePercent": 0.1, "regularMarketTime": 1710500000},
            {"symbol": "^TNX", "regularMarketPrice": 42.0, "regularMarketChange": 0.15, "regularMarketChangePercent": 0.35, "regularMarketTime": 1710500000},
            {"symbol": "NVDA", "regularMarketPrice": 900.0, "regularMarketChangePercent": 1.2, "regularMarketTime": 1710500000},
        ]
        with caplog.at_level(logging.WARNING, logger="src.api.finance"):
            with patch.object(
                finance_client, "_fetch_yahoo_quotes_sync",
                side_effect=Exception("401 Client Error: Unauthorized"),
            ):
                with patch.object(
                    finance_client, "_fetch_yahoo_chart_sync", return_value=mock_rows,
                ):
                    result = await finance_client.get_global_market_context(date(2026, 3, 27))

        assert result["status"] == "ok"
        assert result["degraded"] is True
        # 主源失败不应产生 warning
        warning_messages = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 0, (
            f"fallback 成功时不应有 warning 日志: {[r.message for r in warning_messages]}"
        )

    @pytest.mark.asyncio
    async def test_all_providers_fail_produces_final_warning(self, finance_client, caplog):
        """所有 provider 均失败时应产生一次最终 warning。"""
        with caplog.at_level(logging.DEBUG, logger="src.api.finance"):
            with patch.object(
                finance_client, "_fetch_yahoo_quotes_sync",
                side_effect=Exception("401 Client Error: Unauthorized"),
            ):
                with patch.object(
                    finance_client, "_fetch_yahoo_chart_sync",
                    side_effect=Exception("Connection refused"),
                ):
                    result = await finance_client.get_global_market_context(date(2026, 3, 27))

        assert result["status"] == "error"
        warning_messages = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 1, (
            f"应恰好有 1 条 warning: {[r.message for r in warning_messages]}"
        )
        assert "所有数据源失败" in warning_messages[0].message
        assert "unauthorized" in warning_messages[0].message
        assert "network_error" in warning_messages[0].message

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback_no_warning(self, finance_client, caplog):
        """主源成功时不应产生任何 warning 日志。"""
        mock_rows = [
            {"symbol": "^DJI", "regularMarketPrice": 39000.0, "regularMarketChangePercent": 0.4, "regularMarketTime": 1710500000},
            {"symbol": "^GSPC", "regularMarketPrice": 5200.0, "regularMarketChangePercent": 0.6, "regularMarketTime": 1710500000},
            {"symbol": "^IXIC", "regularMarketPrice": 16500.0, "regularMarketChangePercent": 0.9, "regularMarketTime": 1710500000},
            {"symbol": "^VIX", "regularMarketPrice": 13.5, "regularMarketChangePercent": -2.0, "regularMarketTime": 1710500000},
            {"symbol": "DX-Y.NYB", "regularMarketPrice": 104.1, "regularMarketChangePercent": 0.1, "regularMarketTime": 1710500000},
            {"symbol": "^TNX", "regularMarketPrice": 42.0, "regularMarketChange": 0.15, "regularMarketChangePercent": 0.35, "regularMarketTime": 1710500000},
            {"symbol": "NVDA", "regularMarketPrice": 900.0, "regularMarketChangePercent": 1.2, "regularMarketTime": 1710500000},
        ]
        with caplog.at_level(logging.WARNING, logger="src.api.finance"):
            with patch.object(
                finance_client, "_fetch_yahoo_quotes_sync", return_value=mock_rows,
            ):
                result = await finance_client.get_global_market_context(date(2026, 3, 27))

        assert result["status"] == "ok"
        warning_messages = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 0


# ---------------------------------------------------------------------------
# pytdx 日志测试
# ---------------------------------------------------------------------------


class TestPytdxHostLogging:
    """pytdx 主站遍历日志级别测试。"""

    @pytest.mark.asyncio
    async def test_first_host_fails_later_succeeds_no_warning(self, finance_client, caplog):
        """首个 host 失败但后续成功时不产生默认 warning。"""
        call_count = 0

        from unittest.mock import MagicMock

        def make_api(**kwargs):
            nonlocal call_count
            call_count += 1
            api = MagicMock()
            if call_count == 1:
                # 首个 host: connect 抛异常
                api.connect.side_effect = ConnectionError("模拟首个主站连接失败")
            else:
                # 后续 host: connect 返回成功的 context manager
                success_api = _mock_pytdx_api()
                api.connect.return_value.__enter__ = MagicMock(return_value=success_api)
                api.connect.return_value.__exit__ = MagicMock(return_value=False)
                # 让后续调用也使用真实的 api 方法
                api.get_security_count = success_api.get_security_count
                api.get_security_list = success_api.get_security_list
                api.get_security_quotes = success_api.get_security_quotes
            return api

        with caplog.at_level(logging.WARNING, logger="src.api.finance"):
            with patch("pytdx.hq.TdxHq_API", side_effect=make_api):
                with patch.object(
                    finance_client, "_build_pytdx_a_share_universe",
                    return_value=[(0, "000001"), (0, "000002")],
                ):
                    stats, quality = await finance_client._fetch_pytdx_statistics()

        # 应该有结果（后续 host 成功）
        assert quality["source"] == "pytdx_quotes"
        # WARNING 级别不应有日志（因为最终成功了）
        warning_messages = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 0, (
            f"后续 host 成功时不应有 warning: {[r.message for r in warning_messages]}"
        )

    @pytest.mark.asyncio
    async def test_all_hosts_fail_produces_final_warning(self, finance_client, caplog):
        """全部 host 失败时只产生一次最终 warning。"""
        from unittest.mock import MagicMock

        def make_api(**kwargs):
            api = MagicMock()
            api.connect.side_effect = ConnectionError("连接失败")
            return api

        with caplog.at_level(logging.DEBUG, logger="src.api.finance"):
            with patch("pytdx.hq.TdxHq_API", side_effect=make_api):
                stats, quality = await finance_client._fetch_pytdx_statistics()

        assert stats == {"up_count": 0, "down_count": 0, "flat_count": 0}
        assert quality["status"] == "error"

        warning_messages = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 1, (
            f"应恰好有 1 条 warning: {[r.message for r in warning_messages]}"
        )
        assert "全部主站失败" in warning_messages[0].message
        assert "attempts=" in warning_messages[0].message

        # 单次 host 失败应为 debug 级别
        debug_messages = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "主站尝试失败" in r.message
        ]
        assert len(debug_messages) > 0, "应有 debug 级别的单次 host 失败日志"

    @pytest.mark.asyncio
    async def test_single_host_fail_is_debug_not_warning(self, finance_client, caplog):
        """单个 host 失败应记为 debug 而非 warning。"""
        from unittest.mock import MagicMock

        def make_api(**kwargs):
            api = MagicMock()
            api.connect.side_effect = ConnectionError("连接失败")
            return api

        with caplog.at_level(logging.DEBUG, logger="src.api.finance"):
            with patch("pytdx.hq.TdxHq_API", side_effect=make_api):
                await finance_client._fetch_pytdx_statistics()

        host_failure_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "主站" in r.message and "尝试失败" in r.message
        ]
        assert len(host_failure_warnings) == 0, (
            f"单次 host 失败不应有 warning: {[r.message for r in host_failure_warnings]}"
        )


# ---------------------------------------------------------------------------
# market-summary CLI 日志污染回归测试
# ---------------------------------------------------------------------------


class TestMarketSummaryLoggingPollution:
    """验证 fallback/near-complete 成功路径输出不被可恢复失败日志污染。"""

    @pytest.mark.asyncio
    async def test_fallback_success_path_no_warning_logs(self, finance_client, caplog):
        """海外市场 fallback 成功路径不应在 WARNING 级别产生日志。"""
        mock_rows = [
            {"symbol": "^DJI", "regularMarketPrice": 39000.0, "regularMarketChangePercent": 0.4, "regularMarketTime": 1710500000},
            {"symbol": "^GSPC", "regularMarketPrice": 5200.0, "regularMarketChangePercent": 0.6, "regularMarketTime": 1710500000},
            {"symbol": "^IXIC", "regularMarketPrice": 16500.0, "regularMarketChangePercent": 0.9, "regularMarketTime": 1710500000},
            {"symbol": "^VIX", "regularMarketPrice": 13.5, "regularMarketChangePercent": -2.0, "regularMarketTime": 1710500000},
            {"symbol": "DX-Y.NYB", "regularMarketPrice": 104.1, "regularMarketChangePercent": 0.1, "regularMarketTime": 1710500000},
            {"symbol": "^TNX", "regularMarketPrice": 42.0, "regularMarketChange": 0.15, "regularMarketChangePercent": 0.35, "regularMarketTime": 1710500000},
            {"symbol": "NVDA", "regularMarketPrice": 900.0, "regularMarketChangePercent": 1.2, "regularMarketTime": 1710500000},
        ]
        with caplog.at_level(logging.WARNING, logger="src.api.finance"):
            with patch.object(
                finance_client, "_fetch_yahoo_quotes_sync",
                side_effect=Exception("401 Client Error: Unauthorized"),
            ):
                with patch.object(
                    finance_client, "_fetch_yahoo_chart_sync", return_value=mock_rows,
                ):
                    result = await finance_client.get_global_market_context(date(2026, 3, 27))

        # 结果应该是成功的
        assert result["status"] == "ok"
        assert result["degraded"] is True

        # WARNING 级别不应有日志
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0, (
            f"fallback 成功路径不应有 WARNING 日志: {[r.message for r in warnings]}"
        )
