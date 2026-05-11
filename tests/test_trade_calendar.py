"""交易日辅助函数测试 - 覆盖 is_trade_day、get_previous_trade_date、get_effective_fetch_trade_date。"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.services.trade_calendar import (
    get_effective_fetch_trade_date,
    get_previous_trade_date,
    is_trade_day,
)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# ── 已知日期常量 ──────────────────────────────────────────────
# 2025-01-06 (周一) ~ 2025-01-10 (周五) 为普通工作周
MON = date(2025, 1, 6)
TUE = date(2025, 1, 7)
WED = date(2025, 1, 8)
THU = date(2025, 1, 9)
FRI = date(2025, 1, 10)
SAT = date(2025, 1, 11)
SUN = date(2025, 1, 12)


# ── is_trade_day ──────────────────────────────────────────────


class TestIsTradeDay:
    """测试 is_trade_day 判定逻辑。"""

    def test_weekday_is_trade_day(self) -> None:
        assert is_trade_day(MON) is True

    def test_friday_is_trade_day(self) -> None:
        assert is_trade_day(FRI) is True

    def test_saturday_is_not_trade_day(self) -> None:
        assert is_trade_day(SAT) is False

    def test_sunday_is_not_trade_day(self) -> None:
        assert is_trade_day(SUN) is False

    @patch("src.services.trade_calendar.chinese_calendar.is_workday", return_value=False)
    def test_holiday_weekday_is_not_trade_day(self, _mock: MagicMock) -> None:
        """工作日但法定假日 → 非交易日。"""
        assert is_trade_day(MON) is False

    def test_default_uses_today(self) -> None:
        """不传参数时使用 date.today()。"""
        result = is_trade_day()
        expected = is_trade_day(date.today())
        assert result == expected


# ── get_previous_trade_date ───────────────────────────────────


class TestGetPreviousTradeDate:
    """测试 get_previous_trade_date 回溯逻辑。"""

    def test_monday_returns_friday(self) -> None:
        """周一的前一个交易日是上周五。"""
        prev_fri = date(2025, 1, 3)
        assert get_previous_trade_date(MON) == prev_fri

    def test_tuesday_returns_monday(self) -> None:
        assert get_previous_trade_date(TUE) == MON

    def test_sunday_returns_friday(self) -> None:
        """周日的 previous 仍是周五（跳过周六）。"""
        assert get_previous_trade_date(SUN) == FRI

    @patch("src.services.trade_calendar.chinese_calendar.is_workday", return_value=False)
    def test_skips_holiday(self, _mock: MagicMock) -> None:
        """连续假日回溯到最近的交易日。"""
        # 所有工作日都被标记为假日，只有周末判断生效
        # 这里预期会回溯到第一个非周末的 chinese_calendar.is_workday=True 的日期
        # 但由于 mock 全部返回 False，会触发 ValueError
        with pytest.raises(ValueError, match="30 天内未找到交易日"):
            get_previous_trade_date(MON)

    def test_default_uses_today(self) -> None:
        result = get_previous_trade_date()
        assert isinstance(result, date)
        assert result < date.today()


# ── get_effective_fetch_trade_date ────────────────────────────


class TestGetEffectiveFetchTradeDate:
    """测试 get_effective_fetch_trade_date 09:15 边界逻辑。"""

    def test_weekend_uses_previous_friday(self) -> None:
        """周末 → 使用上周五。"""
        sat_morning = datetime(2025, 1, 11, 10, 0, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(sat_morning)
        assert result == FRI

    def test_sunday_uses_previous_friday(self) -> None:
        """周日 → 使用上周五。"""
        sun_evening = datetime(2025, 1, 12, 20, 0, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(sun_evening)
        assert result == FRI

    def test_trade_day_before_0915_uses_previous(self) -> None:
        """交易日 09:15 之前 → 使用前一交易日。"""
        mon_early = datetime(2025, 1, 6, 8, 0, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(mon_early)
        prev_fri = date(2025, 1, 3)
        assert result == prev_fri

    def test_trade_day_at_0915_uses_today(self) -> None:
        """交易日 09:15 → 使用当天。"""
        mon_at_boundary = datetime(2025, 1, 6, 9, 15, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(mon_at_boundary)
        assert result == MON

    def test_trade_day_after_0915_uses_today(self) -> None:
        """交易日 09:15 之后 → 使用当天。"""
        mon_late = datetime(2025, 1, 6, 15, 30, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(mon_late)
        assert result == MON

    def test_trade_day_midnight_uses_previous(self) -> None:
        """交易日 00:00 → 使用前一交易日。"""
        mon_midnight = datetime(2025, 1, 6, 0, 0, tzinfo=SHANGHAI_TZ)
        result = get_effective_fetch_trade_date(mon_midnight)
        prev_fri = date(2025, 1, 3)
        assert result == prev_fri

    @patch("src.services.trade_calendar.chinese_calendar.is_workday", return_value=False)
    def test_holiday_uses_previous_trade_day(self, _mock: MagicMock) -> None:
        """法定假日（非周末）→ 回溯到前一交易日。

        由于 chinese_calendar 全部返回 False，需要找到周末之前的交易日。
        """
        # 2025-01-06 周一，被 mock 为假日
        # 前一个非周末日 2025-01-03 周五也是假日 (mock)
        # 再往前 2025-01-02 周四也是假日 (mock)
        # 再往前 2025-01-01 周三也是假日 (mock)
        # 再往前 2024-12-31 周二也是假日 (mock)
        # 再往前 2024-12-30 周一也是假日 (mock)
        # 再往前 2024-12-29 周日 (周末) → 跳过
        # 再往前 2024-12-28 周六 (周末) → 跳过
        # 再往前 2024-12-27 周五也是假日 (mock)
        # ... 全部 mock 为 False，会触发 ValueError
        holiday = datetime(2025, 1, 6, 10, 0, tzinfo=SHANGHAI_TZ)
        with pytest.raises(ValueError):
            get_effective_fetch_trade_date(holiday)

    def test_naive_datetime_treated_as_shanghai(self) -> None:
        """传入 naive datetime（无 tzinfo）时也能正确处理。"""
        # 没有 tzinfo 的 datetime，date() 仍能正常提取
        naive = datetime(2025, 1, 6, 15, 0)
        result = get_effective_fetch_trade_date(naive)
        assert result == MON

    def test_default_uses_current_time(self) -> None:
        """不传参数时使用当前时间。"""
        result = get_effective_fetch_trade_date()
        assert isinstance(result, date)
