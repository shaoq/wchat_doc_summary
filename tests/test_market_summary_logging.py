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
