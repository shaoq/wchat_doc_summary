"""A 股交易日辅助函数。

提供轻量级的纯函数用于判断交易日、查找前一交易日、
以及计算 fetch_all() 批量进度所用的有效抓取交易日。

交易日判定采用与 MarketAnalyzer 一致的保守规则：
- 周末永不视为交易日（即使 chinese_calendar 标记为补班日）
- 工作日依赖 chinese_calendar.is_workday() 排除法定假日
"""

import chinese_calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_FETCH_BOUNDARY_HOUR = 9
_FETCH_BOUNDARY_MINUTE = 15
_MAX_LOOKBACK = 30


def is_trade_day(check_date: date | None = None) -> bool:
    """判断给定日期是否为 A 股交易日。

    Args:
        check_date: 待检查日期，默认为今天。

    Returns:
        True 表示交易日，False 表示非交易日。
    """
    if check_date is None:
        check_date = date.today()

    # 周末永不视为交易日
    if check_date.weekday() >= 5:
        return False

    return bool(chinese_calendar.is_workday(check_date))


def get_previous_trade_date(trade_date: date | None = None) -> date:
    """获取给定日期之前的最近交易日。

    Args:
        trade_date: 起始日期，默认为今天。

    Returns:
        前一个交易日。

    Raises:
        ValueError: 在 30 天内未找到交易日。
    """
    if trade_date is None:
        trade_date = date.today()

    check = trade_date - timedelta(days=1)
    for _ in range(_MAX_LOOKBACK):
        if is_trade_day(check):
            return check
        check -= timedelta(days=1)

    raise ValueError(f"在 {trade_date} 之前 {_MAX_LOOKBACK} 天内未找到交易日")


def get_effective_fetch_trade_date(now: datetime | None = None) -> date:
    """计算 fetch_all() 批量进度所用的有效抓取交易日。

    边界规则（09:15 本地时间）：
    - 非交易日（周末/假日）→ 回溯到最近交易日
    - 交易日 09:15 之前 → 使用前一交易日
    - 交易日 09:15 及之后 → 使用当前交易日

    Args:
        now: 可选的当前时间（用于测试注入），默认为当前上海时间。

    Returns:
        有效抓取交易日。
    """
    if now is None:
        now = datetime.now(SHANGHAI_TZ)

    today = now.date()

    # 非交易日：回溯到最近交易日
    if not is_trade_day(today):
        return get_previous_trade_date(today)

    # 交易日：检查是否在 09:15 边界之前
    boundary = now.replace(
        hour=_FETCH_BOUNDARY_HOUR,
        minute=_FETCH_BOUNDARY_MINUTE,
        second=0,
        microsecond=0,
    )

    if now < boundary:
        return get_previous_trade_date(today)

    return today
