"""task 8: get_category_capabilities 单测。

indices/sectors 保持 historical_safe=False（backfill 未接 TickFlow 历史回填，留后续）。
"""

from src.api.finance import FinanceClient


def test_returns_deep_copy():
    caps = FinanceClient.get_category_capabilities()
    caps["indices"]["historical_safe"] = True  # 篡改副本
    assert caps is not FinanceClient.CATEGORY_CAPABILITIES
    # 原常量未受影响
    assert FinanceClient.CATEGORY_CAPABILITIES["indices"]["historical_safe"] is False


def test_indices_sectors_remain_realtime():
    """indices/sectors 保持 historical_safe=False（backfill 接 TickFlow 历史回填留后续）。"""
    caps = FinanceClient.get_category_capabilities()
    assert caps["indices"]["historical_safe"] is False
    assert caps["sectors"]["historical_safe"] is False
    assert caps["volume"]["historical_safe"] is True
    assert caps["limit_up"]["historical_safe"] is True
