"""Test cases for market-summary logging optimization."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date

from src.cli import (
    _format_market_data_summary,
    _format_articles_summary,
    _format_elapsed_time,
)


class TestFormatFunctions:
    """Test helper formatting functions."""

    def test_format_market_data_summary_with_data(self):
        """Test formatting market data with real data."""
        market_data = {
            "indices": {
                "sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045},
                "sz": {"name": "深证成指", "close": 9876.54, "change": 0.0032},
            },
            "volume": {"total_volume": 12000},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
        }
        result = _format_market_data_summary(market_data)
        assert "上证 3089.26 (+0.45%)" in result
        assert "深证 9876.54 (+0.32%)" in result
        assert "成交: 1.2万亿" in result
        assert "涨跌: 2500/1800/200" in result

    def test_format_market_data_summary_empty(self):
        """Test formatting empty market data."""
        market_data = {
            "indices": {},
            "volume": {},
            "statistics": {},
        }
        result = _format_market_data_summary(market_data)
        assert "指数: 无数据" in result

        assert "成交: 0亿" in result

    def test_format_market_data_summary_large_volume(self):
        """Test formatting large volume (万亿+)."""
        market_data = {
            "indices": {"sh": {"name": "上证指数", "close": 3000, "change": 0.01}},
            "volume": {"total_volume": 15000},
            "statistics": {},
        }
        result = _format_market_data_summary(market_data)
        assert "成交: 1.5万亿" in result

    def test_format_articles_summary(self):
        """Test formatting articles summary."""
        articles = [{"title": f"Article {i}"} for i in range(15)]
        result = _format_articles_summary(articles)
        assert "找到 15 篇文章 (最近 3 天)" == result

    def test_format_articles_summary_empty(self):
        """Test formatting empty articles."""
        articles = []
        result = _format_articles_summary(articles)
        assert "找到 0 篇文章 (最近 3 天)" == result

    def test_format_elapsed_time(self):
        """Test formatting elapsed time."""
        assert _format_elapsed_time(3.14159) == "3.1s"
        assert _format_elapsed_time(0.5) == "0.5s"
        assert _format_elapsed_time(123.456) == "123.5s"


# ---------------------------------------------------------------------------
# 静默输出治理测试
# ---------------------------------------------------------------------------


class TestSilenceTqdm:
    """测试 _silence_tqdm 上下文管理器的行为。"""

    def test_silence_tqdm_sets_and_restores_env(self):
        """_silence_tqdm 应临时设置 TQDM_DISABLE 并在退出时恢复。"""
        import os
        from src.api.finance import _silence_tqdm

        # 确保初始状态干净
        os.environ.pop("TQDM_DISABLE", None)

        with _silence_tqdm():
            assert os.environ.get("TQDM_DISABLE") == "1"

        # 退出后应恢复
        assert "TQDM_DISABLE" not in os.environ

    def test_silence_tqdm_restores_previous_value(self):
        """_silence_tqdm 应恢复之前已有的 TQDM_DISABLE 值。"""
        import os
        from src.api.finance import _silence_tqdm

        os.environ["TQDM_DISABLE"] = "0"
        try:
            with _silence_tqdm():
                assert os.environ.get("TQDM_DISABLE") == "1"
            # 退出后应恢复之前的值
            assert os.environ.get("TQDM_DISABLE") == "0"
        finally:
            os.environ.pop("TQDM_DISABLE", None)

    def test_silence_tqdm_restores_on_exception(self):
        """_silence_tqdm 即使在异常时也应恢复环境变量。"""
        import os
        from src.api.finance import _silence_tqdm

        os.environ.pop("TQDM_DISABLE", None)

        with pytest.raises(RuntimeError):
            with _silence_tqdm():
                assert os.environ.get("TQDM_DISABLE") == "1"
                raise RuntimeError("test error")

        assert "TQDM_DISABLE" not in os.environ


class TestSharedFallbackSnapshotHelpers:
    """测试共享备用快照的辅助计算方法。"""

    def test_compute_volume_from_spot_em_df(self):
        """_compute_volume_from_spot_em_df 应正确计算两市成交额。"""
        import pandas as pd
        from src.api.finance import FinanceClient

        client = FinanceClient()
        df = pd.DataFrame({
            "代码": ["600000", "000001", "300001"],
            "成交额": [500000000, 300000000, 200000000],
        })
        result = client._compute_volume_from_spot_em_df(df)
        assert result["total_volume"] > 0
        assert result["sh_volume"] == 5.0
        assert result["sz_volume"] == 5.0  # 000001 + 300001
        assert result["total_volume"] == 10.0

    def test_compute_statistics_from_spot_em_df(self):
        """_compute_statistics_from_spot_em_df 应正确计算涨跌统计。"""
        import pandas as pd
        from src.api.finance import FinanceClient

        client = FinanceClient()
        df = pd.DataFrame({
            "代码": ["600000", "000001", "300001"],
            "涨跌幅": [2.0, -1.0, 0.0],
        })
        result = client._compute_statistics_from_spot_em_df(df)
        assert result["up_count"] == 1
        assert result["down_count"] == 1
        assert result["flat_count"] == 1

    def test_compute_volume_from_empty_df(self):
        """空 DataFrame 应返回零值。"""
        import pandas as pd
        from src.api.finance import FinanceClient

        client = FinanceClient()
        df = pd.DataFrame(columns=["代码", "成交额"])
        result = client._compute_volume_from_spot_em_df(df)
        assert result == {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    def test_compute_statistics_from_empty_df(self):
        """空 DataFrame 应返回零值。"""
        import pandas as pd
        from src.api.finance import FinanceClient

        client = FinanceClient()
        df = pd.DataFrame(columns=["代码", "涨跌幅"])
        result = client._compute_statistics_from_spot_em_df(df)
        assert result == {"up_count": 0, "down_count": 0, "flat_count": 0}
