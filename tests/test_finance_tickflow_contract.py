"""finance.py TickFlow 分流的 dict 契约 + 口径单测（纯函数，不触网）。"""

from src.api.finance import FinanceClient
from src.api.market_providers.base import (
    IndexQuote,
    LimitUpRow,
    SectorResult,
    SectorRow,
)


def test_tf_indices_to_dict_nested_and_keeps_decimal():
    """{sh: IndexQuote} → {sh: {name, close, change}}，change 保持小数。"""
    d = FinanceClient._tf_indices_to_dict(
        {"sh": IndexQuote("上证指数", 3764.15, -0.0305)}
    )
    assert d["sh"] == {"name": "上证指数", "close": 3764.15, "change": -0.0305}


def test_tf_indices_to_dict_empty():
    assert FinanceClient._tf_indices_to_dict(None) == {}
    assert FinanceClient._tf_indices_to_dict({}) == {}


def test_tf_sectors_to_dict_contract():
    """SectorResult → {top_sectors, bottom_sectors}，change 小数。"""
    r = SectorResult(
        top_sectors=[SectorRow("SW1_A", "行业A", 0.0522)],
        bottom_sectors=[SectorRow("SW1_B", "行业B", -0.0311)],
    )
    d = FinanceClient._tf_sectors_to_dict(r)
    assert d["top_sectors"] == [{"name": "行业A", "code": "SW1_A", "change": 0.0522}]
    assert d["bottom_sectors"][0]["change"] == -0.0311


def test_tf_sectors_to_dict_empty():
    assert FinanceClient._tf_sectors_to_dict(None) == {
        "top_sectors": [],
        "bottom_sectors": [],
    }


def test_tf_limit_up_to_list_contract():
    """[LimitUpRow] → [{name, code, change}]，change 小数。"""
    d = FinanceClient._tf_limit_up_to_list(
        [LimitUpRow("600000.SH", "浦发银行", 0.1009)]
    )
    assert d == [{"name": "浦发银行", "code": "600000.SH", "change": 0.1009}]


def test_tf_limit_up_to_list_empty():
    assert FinanceClient._tf_limit_up_to_list(None) == []
    assert FinanceClient._tf_limit_up_to_list([]) == []
