"""交易日边界测试 - 测试 MarketAnalyzer 的交易日判断、窗口计算与回退逻辑。"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.market_analyzer import MarketAnalyzer


class TestIsTradeDay:
    """测试 is_trade_day 的保守 A 股规则。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例（不需要真实数据库，仅测纯逻辑方法）。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    # ---- 普通工作日 ----

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_monday_is_trade_day(self, mock_calendar, analyzer):
        """周一应为交易日。"""
        mock_calendar.is_workday.return_value = True
        # 2026-03-30 是周一
        assert analyzer.is_trade_day(date(2026, 3, 30)) is True

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_friday_is_trade_day(self, mock_calendar, analyzer):
        """周五应为交易日。"""
        mock_calendar.is_workday.return_value = True
        # 2026-03-27 是周五
        assert analyzer.is_trade_day(date(2026, 3, 27)) is True

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_midweek_is_trade_day(self, mock_calendar, analyzer):
        """周三应为交易日（普通工作日）。"""
        mock_calendar.is_workday.return_value = True
        # 2026-03-25 是周三
        assert analyzer.is_trade_day(date(2026, 3, 25)) is True

    # ---- 周末 ----

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_saturday_is_not_trade_day(self, mock_calendar, analyzer):
        """周六不是交易日（weekday() == 5，先返回 False）。"""
        # 即使 chinese_calendar 认为是工作日也应排除
        mock_calendar.is_workday.return_value = True
        # 2026-03-28 是周六
        assert analyzer.is_trade_day(date(2026, 3, 28)) is False
        # weekday() >= 5 先返回 False，不会调用 calendar.is_workday
        mock_calendar.is_workday.assert_not_called()

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_sunday_is_not_trade_day(self, mock_calendar, analyzer):
        """周日不是交易日（weekday() == 6，先返回 False）。"""
        mock_calendar.is_workday.return_value = True
        # 2026-03-29 是周日
        assert analyzer.is_trade_day(date(2026, 3, 29)) is False
        mock_calendar.is_workday.assert_not_called()

    # ---- 法定节假日 ----

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_holiday_is_not_trade_day(self, mock_calendar, analyzer):
        """法定节假日不是交易日（calendar.is_workday 返回 False）。"""
        mock_calendar.is_workday.return_value = False
        # 2026-01-01 元旦（周四）
        assert analyzer.is_trade_day(date(2026, 1, 1)) is False

    # ---- 调休工作日周末 ----

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_adjusted_workday_weekend_still_not_trade_day(self, mock_calendar, analyzer):
        """调休工作日周末仍不是交易日（保守规则：weekday() >= 5 先返回 False）。

        chinese_calendar.is_workday 可能把周末调休标记为工作日，
        但 is_trade_day 的保守规则会在 weekday() >= 5 时直接返回 False，
        不调用 calendar.is_workday。
        """
        mock_calendar.is_workday.return_value = True
        # 构造一个周六日期（无论 chinese_calendar 怎么说）
        saturday = date(2026, 3, 28)  # 周六
        assert saturday.weekday() == 5
        assert analyzer.is_trade_day(saturday) is False
        mock_calendar.is_workday.assert_not_called()

    # ---- 默认参数 ----

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_none_defaults_to_today(self, mock_calendar, analyzer):
        """传入 None 时默认使用今天。"""
        mock_calendar.is_workday.return_value = True
        today = date.today()
        result = analyzer.is_trade_day(None)
        # 结果取决于今天是周几
        if today.weekday() >= 5:
            assert result is False
        else:
            assert result is True


class TestGetNextTradeDate:
    """测试 get_next_trade_date 正确跨越非交易日。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_next_trade_date_skips_weekend(self, mock_calendar, analyzer):
        """周五的下一个交易日应为周一（跨越周末）。"""
        # 2026-03-27 周五 -> 下一个交易日应为 2026-03-30 周一
        # 周六(28) weekday=5 -> False
        # 周日(29) weekday=6 -> False
        # 周一(30) weekday=0 -> is_workday=True
        def is_workday_side_effect(d):
            # 周末已被 weekday() >= 5 过滤，不会走到这里
            # 仅工作日会调用
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        result = analyzer.get_next_trade_date(date(2026, 3, 27))
        assert result == date(2026, 3, 30)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_next_trade_date_consecutive_workday(self, mock_calendar, analyzer):
        """周一的下一个交易日应为周二。"""
        mock_calendar.is_workday.return_value = True
        # 2026-03-30 周一 -> 下一个交易日 2026-03-31 周二
        result = analyzer.get_next_trade_date(date(2026, 3, 30))
        assert result == date(2026, 3, 31)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_next_trade_date_skips_holiday(self, mock_calendar, analyzer):
        """遇到法定节假日应跳过。"""
        # 2026-01-01 周四（元旦）-> 应跳过
        # 模拟：12/31 是交易日，1/1 是节假日，1/2 是交易日
        def is_workday_side_effect(d):
            if d == date(2026, 1, 1):
                return False  # 元旦放假
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        # 2025-12-31 周三 -> 下一个交易日跳过 1/1，应为 1/2 周五
        result = analyzer.get_next_trade_date(date(2025, 12, 31))
        assert result == date(2026, 1, 2)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_next_trade_date_raises_when_not_found(self, mock_calendar, analyzer):
        """30 天内找不到交易日时应抛出 ValueError。"""
        mock_calendar.is_workday.return_value = False
        with pytest.raises(ValueError, match="30 天内未找到下一个交易日"):
            analyzer.get_next_trade_date(date(2026, 3, 27))


class TestCalculateArticleTimeWindow:
    """测试 calculate_article_time_window 精确窗口计算。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_window_precise_boundaries(self, mock_calendar, analyzer):
        """时间窗口应为 trade_date 15:00 ~ next_trading_date 09:15。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三
        # 下一个交易日 = 2026-03-26 周四

        start, end = analyzer.calculate_article_time_window(trade_date)

        assert start == datetime(2026, 3, 25, 15, 0)
        assert end == datetime(2026, 3, 26, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_window_friday_to_monday(self, mock_calendar, analyzer):
        """周五到周一的窗口跨越（周五 15:00 ~ 周一 09:15）。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 27)  # 周五
        # 下一个交易日 = 2026-03-30 周一（跨越周六、周日）

        start, end = analyzer.calculate_article_time_window(trade_date)

        assert start == datetime(2026, 3, 27, 15, 0)
        assert end == datetime(2026, 3, 30, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_window_before_holiday(self, mock_calendar, analyzer):
        """节假日前一天的窗口应跨越假期。"""
        def is_workday_side_effect(d):
            if d == date(2026, 1, 1):
                return False  # 元旦放假
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        trade_date = date(2025, 12, 31)  # 周三
        # 下一个交易日跳过 1/1（元旦），应为 1/2 周五

        start, end = analyzer.calculate_article_time_window(trade_date)

        assert start == datetime(2025, 12, 31, 15, 0)
        assert end == datetime(2026, 1, 2, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_window_duration_friday_to_monday(self, mock_calendar, analyzer):
        """周五到周一窗口时长应为 3 天（跨周末）。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 27)  # 周五

        start, end = analyzer.calculate_article_time_window(trade_date)
        duration = end - start

        # 2026-03-27 15:00 ~ 2026-03-30 09:15
        # = 2 天 18 小时 15 分钟
        expected_duration = timedelta(days=2, hours=18, minutes=15)
        assert duration == expected_duration

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_window_duration_consecutive_days(self, mock_calendar, analyzer):
        """相邻交易日窗口时长应为 18 小时 15 分钟。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三

        start, end = analyzer.calculate_article_time_window(trade_date)
        duration = end - start

        # 2026-03-25 15:00 ~ 2026-03-26 09:15
        # = 18 小时 15 分钟
        expected_duration = timedelta(hours=18, minutes=15)
        assert duration == expected_duration


class TestGetLatestTradeDate:
    """测试 get_latest_trade_date 非交易日回退逻辑。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_saturday_falls_back_to_friday(self, mock_calendar, analyzer):
        """周六应回退到最近的交易日（周五）。"""
        mock_calendar.is_workday.return_value = True
        # 使用一个确定的未来周六（非今天），避免 get_latest_trade_date 的 today 分支
        saturday = date(2026, 4, 4)  # 周六

        result = analyzer.get_latest_trade_date(target_date=saturday)
        assert result == date(2026, 4, 3)  # 周五

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_sunday_falls_back_to_friday(self, mock_calendar, analyzer):
        """周日应回退到最近的交易日（周五）。"""
        mock_calendar.is_workday.return_value = True
        # 使用确定的未来周日（非今天）
        sunday = date(2026, 4, 5)  # 周日

        result = analyzer.get_latest_trade_date(target_date=sunday)
        assert result == date(2026, 4, 3)  # 周五

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_holiday_falls_back_to_previous_trade_day(self, mock_calendar, analyzer):
        """法定节假日应回退到前一个交易日。"""
        def is_workday_side_effect(d):
            if d == date(2026, 1, 1):
                return False  # 元旦放假
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        new_year = date(2026, 1, 1)  # 元旦（周四）
        result = analyzer.get_latest_trade_date(target_date=new_year)
        assert result == date(2025, 12, 31)  # 周三

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_trade_day_returns_itself(self, mock_calendar, analyzer):
        """交易日应返回自身（非今天场景）。"""
        mock_calendar.is_workday.return_value = True
        wednesday = date(2026, 3, 25)  # 周三

        result = analyzer.get_latest_trade_date(target_date=wednesday)
        assert result == wednesday

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_long_holiday_falls_back_multiple_days(self, mock_calendar, analyzer):
        """长假期间应持续回退到最近交易日。"""
        def is_workday_side_effect(d):
            # 模拟春节长假: 2/16 ~ 2/22 均为非交易日
            holiday_start = date(2026, 2, 16)
            holiday_end = date(2026, 2, 22)
            if holiday_start <= d <= holiday_end:
                return False
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        # 2/20 周五（假期中）-> 应回退到 2/13 周五（节前最后一个交易日）
        # 注意：2/15 是周日，2/14 是周六，所以节前最后一个工作日是 2/13 周五
        result = analyzer.get_latest_trade_date(target_date=date(2026, 2, 20))
        assert result == date(2026, 2, 13)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_degradation_when_no_trade_day_found(self, mock_calendar, analyzer):
        """30 天内找不到交易日时降级返回目标日期。"""
        mock_calendar.is_workday.return_value = False
        target = date(2026, 3, 28)

        result = analyzer.get_latest_trade_date(target_date=target)
        # 降级处理：返回 target_date
        assert result == target

    @patch("src.services.market_analyzer.date")
    @patch("src.services.trade_calendar.chinese_calendar")
    def test_today_is_saturday_falls_back_to_friday(self, mock_calendar, mock_date, analyzer):
        """今天为周六时，get_latest_trade_date() 应回退到周五。"""
        mock_calendar.is_workday.return_value = True
        saturday = date(2026, 4, 4)  # 周六
        mock_date.today.return_value = saturday

        result = analyzer.get_latest_trade_date()
        assert result == date(2026, 4, 3)  # 周五

    @patch("src.services.market_analyzer.date")
    @patch("src.services.trade_calendar.chinese_calendar")
    def test_today_is_sunday_falls_back_to_friday(self, mock_calendar, mock_date, analyzer):
        """今天为周日时，get_latest_trade_date() 应回退到周五。"""
        mock_calendar.is_workday.return_value = True
        sunday = date(2026, 4, 5)  # 周日
        mock_date.today.return_value = sunday

        result = analyzer.get_latest_trade_date()
        assert result == date(2026, 4, 3)  # 周五

    @patch("src.services.market_analyzer.datetime")
    @patch("src.services.market_analyzer.date")
    @patch("src.services.trade_calendar.chinese_calendar")
    def test_trade_day_before_open_uses_previous(self, mock_calendar, mock_date, mock_datetime, analyzer):
        """交易日开盘前应使用上一个交易日。"""
        mock_calendar.is_workday.return_value = True
        monday = date(2026, 3, 30)  # 周一
        mock_date.today.return_value = monday

        # 模拟当前时间 08:30（开盘前）
        mock_datetime.now.return_value = datetime(2026, 3, 30, 8, 30, 0)
        mock_datetime.combine = datetime.combine

        result = analyzer.get_latest_trade_date()
        assert result == date(2026, 3, 27)  # 上周五

    @patch("src.services.market_analyzer.datetime")
    @patch("src.services.market_analyzer.date")
    @patch("src.services.trade_calendar.chinese_calendar")
    def test_trade_day_after_open_returns_today(self, mock_calendar, mock_date, mock_datetime, analyzer):
        """交易日开盘后应返回今天。"""
        mock_calendar.is_workday.return_value = True
        monday = date(2026, 3, 30)  # 周一
        mock_date.today.return_value = monday

        # 模拟当前时间 10:00（开盘后）
        mock_datetime.now.return_value = datetime(2026, 3, 30, 10, 0, 0)
        mock_datetime.combine = datetime.combine

        result = analyzer.get_latest_trade_date()
        assert result == monday


class TestGetPreviousTradeDate:
    """测试 get_previous_trade_date 回溯逻辑。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_monday_previous_is_friday(self, mock_calendar, analyzer):
        """周一的上一个交易日应为上周五。"""
        mock_calendar.is_workday.return_value = True
        monday = date(2026, 3, 30)  # 周一

        result = analyzer.get_previous_trade_date(monday)
        assert result == date(2026, 3, 27)  # 上周五

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_consecutive_day_previous(self, mock_calendar, analyzer):
        """周四的上一个交易日应为周三。"""
        mock_calendar.is_workday.return_value = True
        thursday = date(2026, 3, 26)  # 周四

        result = analyzer.get_previous_trade_date(thursday)
        assert result == date(2026, 3, 25)  # 周三

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_raises_when_no_previous_found(self, mock_calendar, analyzer):
        """30 天内找不到上一个交易日时应抛出 ValueError。"""
        mock_calendar.is_workday.return_value = False
        with pytest.raises(ValueError, match="30 天内未找到交易日"):
            analyzer.get_previous_trade_date(date(2026, 3, 30))


class TestCalculateWatchTimeWindow:
    """测试 calculate_watch_time_window 看盘窗口计算。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_watch_window_regular_trading_day(self, mock_calendar, analyzer):
        """看盘窗口应为 trade_date 09:00 ~ trade_date 15:00。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三

        start, end = analyzer.calculate_watch_time_window(trade_date)

        assert start == datetime(2026, 3, 25, 9, 0)
        assert end == datetime(2026, 3, 25, 15, 0)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_watch_window_friday(self, mock_calendar, analyzer):
        """周五看盘窗口应仅为周五 09:00 ~ 15:00，不跨越周末。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 27)  # 周五

        start, end = analyzer.calculate_watch_time_window(trade_date)

        assert start == datetime(2026, 3, 27, 9, 0)
        assert end == datetime(2026, 3, 27, 15, 0)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_watch_window_duration(self, mock_calendar, analyzer):
        """看盘窗口时长应为 6 小时。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三

        start, end = analyzer.calculate_watch_time_window(trade_date)
        duration = end - start

        assert duration == timedelta(hours=6)


class TestCalculateTelegraphTimeWindow:
    """测试 calculate_telegraph_time_window 电报窗口计算。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_telegraph_window_regular_trading_day(self, mock_calendar, analyzer):
        """电报窗口应为 trade_date 09:00 ~ next_trade_date 09:15。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三

        start, end = analyzer.calculate_telegraph_time_window(trade_date)

        assert start == datetime(2026, 3, 25, 9, 0)
        assert end == datetime(2026, 3, 26, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_telegraph_window_friday_to_monday(self, mock_calendar, analyzer):
        """周五电报窗口应从周五 09:00 到周一 09:15（跨越周末）。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 27)  # 周五

        start, end = analyzer.calculate_telegraph_time_window(trade_date)

        assert start == datetime(2026, 3, 27, 9, 0)
        assert end == datetime(2026, 3, 30, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_telegraph_window_crosses_holiday(self, mock_calendar, analyzer):
        """电报窗口应跨越节假日。"""
        def is_workday_side_effect(d):
            if d == date(2026, 1, 1):
                return False
            return True
        mock_calendar.is_workday.side_effect = is_workday_side_effect

        trade_date = date(2025, 12, 31)  # 周三

        start, end = analyzer.calculate_telegraph_time_window(trade_date)

        assert start == datetime(2025, 12, 31, 9, 0)
        assert end == datetime(2026, 1, 2, 9, 15)


class TestCalculateArticleTimeWindowRefined:
    """测试 calculate_article_time_window 文章窗口（Change 2 确认）。"""

    @pytest.fixture
    def analyzer(self):
        """创建 MarketAnalyzer 实例。"""
        return MarketAnalyzer.__new__(MarketAnalyzer)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_article_window_regular_trading_day(self, mock_calendar, analyzer):
        """文章窗口应为 trade_date 15:00 ~ next_trade_date 09:15。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 25)  # 周三

        start, end = analyzer.calculate_article_time_window(trade_date)

        assert start == datetime(2026, 3, 25, 15, 0)
        assert end == datetime(2026, 3, 26, 9, 15)

    @patch("src.services.trade_calendar.chinese_calendar")
    def test_article_window_friday_to_monday(self, mock_calendar, analyzer):
        """周五文章窗口应为周五 15:00 ~ 周一 09:15。"""
        mock_calendar.is_workday.return_value = True
        trade_date = date(2026, 3, 27)  # 周五

        start, end = analyzer.calculate_article_time_window(trade_date)

        assert start == datetime(2026, 3, 27, 15, 0)
        assert end == datetime(2026, 3, 30, 9, 15)
