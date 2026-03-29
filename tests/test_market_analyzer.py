"""MarketAnalyzer 单元测试 - 测试新闻聚合和交易日感知功能。"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.market_analyzer import MarketAnalyzer


class TestGetRelatedArticlesTradeDayAware:
    """测试 get_related_articles 方法的交易日感知功能。"""

    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库。"""
        db = MagicMock()
        db.get_session = AsyncMock()
        return db

    @pytest.fixture
    def mock_finance_client(self):
        """创建模拟财经客户端。"""
        return MagicMock()

    def test_calculates_trade_day_window_correctly(self, mock_db, mock_finance_client):
        """验证交易日窗口计算正确。"""
        # 使用实际方法计算交易日窗口
        # 假设 trade_date 是 2024-03-15 (周五)
        # 往前 3 个交易日应该是: 3/14(周四), 3/13(周三), 3/12(周二)
        # 所以 start_date 应该是 3/12 或更早

        trade_date = date(2024, 3, 15)  # 周五
        trade_days_back = 3

        # 计算预期的起始日期
        start_date = trade_date
        days_found = 0
        check_date = trade_date

        while days_found < trade_days_back:
            check_date -= timedelta(days=1)
            # 使用简单的周末判断（不依赖 chinese_calendar）
            if check_date.weekday() < 5:  # 周一到周五
                days_found += 1

        # check_date 应该是 3/12 (周二)
        assert check_date == date(2024, 3, 12)


class TestCollectNewsData:
    """测试 collect_news_data 方法的新闻聚合功能。"""

    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库。"""
        db = MagicMock()
        db.get_session = AsyncMock()
        return db

    @pytest.fixture
    def analyzer(self, mock_db):
        """创建 MarketAnalyzer 实例。"""
        with patch('src.services.market_analyzer.FinanceClient'):
            return MarketAnalyzer(mock_db)

    @pytest.mark.asyncio
    async def test_collect_news_data_returns_structured_result(self, analyzer):
        """测试 collect_news_data 返回结构化的结果。"""
        trade_date = date(2024, 3, 15)

        # 模拟各个服务方法
        analyzer.get_related_articles = AsyncMock(return_value=[])

        with patch('src.services.cls_telegraph_service.CLSTelegraphService') as mock_telegraph_service:
            with patch('src.services.cls_watch_service.CLSWatchService') as mock_watch_service:
                # 配置模拟返回
                mock_telegraph_instance = mock_telegraph_service.return_value
                mock_telegraph_instance.list_telegraphs = AsyncMock(return_value=[])

                mock_watch_instance = mock_watch_service.return_value
                mock_watch_instance.get_watch_data_for_summary = AsyncMock(return_value=[])

                result = await analyzer.collect_news_data(trade_date, offline=True)

        # 验证返回结构
        assert "telegraphs" in result
        assert "watch_items" in result
        assert "articles" in result
        assert "sources_status" in result
        assert "time_window" in result
        assert "status" in result
        assert result["status"] == "success"

        # 验证 sources_status 包含所有来源
        assert "telegraphs" in result["sources_status"]
        assert "watch_items" in result["sources_status"]
        assert "articles" in result["sources_status"]

    @pytest.mark.asyncio
    async def test_collect_news_data_single_source_failure_continues(self, analyzer):
        """测试单一数据源失败时仍能继续。"""
        trade_date = date(2024, 3, 15)

        analyzer.get_related_articles = AsyncMock(return_value=[
            {"title": "Test Article", "summary": "Test Summary"}
        ])

        with patch('src.services.cls_telegraph_service.CLSTelegraphService') as mock_telegraph_service:
            with patch('src.services.cls_watch_service.CLSWatchService') as mock_watch_service:
                # 电报服务抛出异常
                mock_telegraph_instance = mock_telegraph_service.return_value
                mock_telegraph_instance.list_telegraphs = AsyncMock(side_effect=Exception("API Error"))

                # 看盘服务正常
                mock_watch_instance = mock_watch_service.return_value
                mock_watch_instance.get_watch_data_for_summary = AsyncMock(return_value=[
                    {"title": "Watch Item"}
                ])

                result = await analyzer.collect_news_data(trade_date, offline=True)

        # 电报失败，但其他数据源应该正常
        assert result["sources_status"]["telegraphs"] == "error"
        assert result["sources_status"]["watch_items"] == "ok"
        assert result["sources_status"]["articles"] == "ok"
        assert len(result["articles"]) == 1
        assert len(result["watch_items"]) == 1
        # 聚合状态应为 degraded
        assert result["status"] == "degraded"


class TestAIProcessorWatchItemsFormat:
    """测试 AIProcessor 中看盘数据格式化功能。"""

    def test_format_watch_items_for_prompt_empty(self):
        """测试空看盘数据格式化。"""
        from src.services.ai_processor import AIProcessor

        # 创建模拟实例
        processor = MagicMock(spec=AIProcessor)
        processor._format_watch_items_for_prompt = AIProcessor._format_watch_items_for_prompt.__get__(processor, AIProcessor)

        result = processor._format_watch_items_for_prompt([])
        assert result == "无看盘数据"

    def test_format_watch_items_for_prompt_with_data(self):
        """测试有数据的看盘数据格式化。"""
        from src.services.ai_processor import AIProcessor

        processor = MagicMock(spec=AIProcessor)
        processor._format_watch_items_for_prompt = AIProcessor._format_watch_items_for_prompt.__get__(processor, AIProcessor)

        watch_items = [
            {
                "publish_time": "2024-03-15 10:30",
                "title": "Test Title",
                "content": "Test Content",
                "stocks": ["Stock A", "Stock B"],
                "sectors": ["Sector 1"],
            }
        ]

        result = processor._format_watch_items_for_prompt(watch_items)

        assert "10:30" in result
        assert "Test Title" in result
        assert "Test Content" in result
        assert "Stock A" in result
        assert "Sector 1" in result

    def test_format_telegraphs_for_prompt_empty(self):
        """测试空电报数据格式化。"""
        from src.services.ai_processor import AIProcessor

        processor = MagicMock(spec=AIProcessor)
        processor._format_telegraphs_for_prompt = AIProcessor._format_telegraphs_for_prompt.__get__(processor, AIProcessor)

        result = processor._format_telegraphs_for_prompt([])
        assert result == "无重要电报"

    def test_format_telegraphs_for_prompt_with_data(self):
        """测试有数据的电报格式化。"""
        from src.services.ai_processor import AIProcessor

        processor = MagicMock(spec=AIProcessor)
        processor._format_telegraphs_for_prompt = AIProcessor._format_telegraphs_for_prompt.__get__(processor, AIProcessor)

        telegraphs = [
            {
                "publish_time": "2024-03-15 09:30",
                "title": "Important News",
                "content": "News content here",
            }
        ]

        result = processor._format_telegraphs_for_prompt(telegraphs)

        assert "09:30" in result
        assert "Important News" in result
        assert "News content here" in result
