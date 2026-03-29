"""实现: 优化 get_latest_trade_date 方法"""

from datetime import date, datetime, timedelta
import chinese_calendar as calendar


def get_latest_trade_date_improved(target_date: date | None = None) -> date:
    """改进版的获取最近交易日。

    智能判断逻辑:
    - 交易日 09:00 前 -> 返回上一个交易日
    - 交易日 09:00 后 -> 返回今天
    - 非交易日 -> 返回最近交易日

    Args:
        target_date: 目标日期, 默认为今天

    Returns:
            最近的交易日
    """
    if target_date is None:
        target_date = date.today()

    # 智能判断: 如果今天是交易日且还没开市(09:00 前), 返回上一个交易日
    if target_date == date.today():
        now = datetime.now()
        market_open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)

        # 如果今天是交易日且还没开市. 返回上一个交易日
        if calendar.is_workday(target_date) and now < market_open_time:
            check_date = target_date - timedelta(days=1)
            for _ in range(30):
                if calendar.is_workday(check_date):
                    return check_date
                check_date -= timedelta(days=1)
            # 如果没找到上一个交易日, 降级使用今天
            return target_date
        # 已开市或返回今天
        return target_date

    # 非交易日: 往前找最近的交易日
    check_date = target_date
    max_days_back = 30

    for _ in range(max_days_back):
        if calendar.is_workday(check_date):
            return check_date
        check_date -= timedelta(days=1)

    # 如果 30 天内找不到, 返回 target_date(降级处理)
    return target_date


# 测试代码
if __name__ == "__main__":
    # 测试 1: 交易日 07:00 - 应返回上一个交易日
    print("测试 1: 交易日 07:00")
    with patch('datetime.datetime') as mock_now:
        mock_now.now.return_value = datetime(2026, 3, 26, 7, 0, 0)
        result = get_latest_trade_date_improved()
        expected = date(2026, 3, 25)
        assert result == expected, f"失败: 应返回 {expected}, 实际返回 {result}"
    print("  通过!")
    # 测试 2: 交易日 10:00 - 应返回今天
    print("测试 2: 交易日 10:00")
    with patch('datetime.datetime') as mock_now:
        mock_now.now.return_value = datetime(2026, 3, 26, 10, 0, 0)
        result = get_latest_trade_date_improved()
        expected = date(2026, 3, 26)
        assert result == expected, f"失败: 应返回 {expected}, 实际返回 {result}"
    print("  通过!")
    # 测试 3: 非交易日 (周六) - 应返回周五
    print("测试 3: 非交易日 (周六)")
    with patch('datetime.datetime') as mock_now:
        mock_now.now.return_value = datetime(2026, 3, 28, 10, 0, 0)
        result = get_latest_trade_date_improved()
        expected = date(2026, 3, 27)
        assert result == expected, f"失败: 应返回 {expected}, 实际返回 {result}"
    print("  通过!")
    print("\n所有测试通过!")
