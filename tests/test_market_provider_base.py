"""Provider 抽象层 + factory 单测。"""

import pytest

from src.api.market_providers.base import (
    BreadthStatistics,
    IndexQuote,
    LimitUpRow,
    MarketDataProvider,
    SectorResult,
    SectorRow,
    SnapshotRow,
    VolumeData,
)
from src.api.market_providers.factory import build_provider_chain


class _StubProvider(MarketDataProvider):
    """测试用 stub，仅实现 get_indices。"""

    name = "stub"
    supports_historical = True

    async def get_indices(self, trade_date=None):  # type: ignore[override]
        return {"sh": IndexQuote("上证指数", 3000.0, 0.0123)}


def test_index_quote_frozen():
    q = IndexQuote("上证指数", 3000.0, 0.0123)
    with pytest.raises(Exception):
        q.price = 3100.0  # type: ignore[misc]


def test_sector_result_default_empty_lists():
    r = SectorResult()
    assert r.top_sectors == []
    assert r.bottom_sectors == []


def test_dataclass_fields_align_contract():
    """dataclass 字段对齐 FinanceClient dict 契约 / schema 表字段。"""
    v = VolumeData(sh_volume=100.0, sz_volume=200.0, total_volume=300.0)
    assert v.total_volume == 300.0

    s = BreadthStatistics(up_count=10, down_count=5, flat_count=2)
    assert s.up_count == 10

    sec = SectorRow(sector_code="SW1_480401", sector_name="银行", change_pct=0.03)
    assert sec.main_inflow is None

    lu = LimitUpRow(stock_code="600000.SH", stock_name="浦发银行", change_pct=0.1)
    assert lu.limit_days is None

    snap = SnapshotRow(symbol="600000.SH", name="浦发银行", price=10.0, change_pct=0.05)
    assert snap.amount is None


@pytest.mark.asyncio
async def test_unimplemented_method_returns_none():
    """未实现的方法默认返回 None（编排层据此 fallback）。"""
    p = _StubProvider()
    assert await p.get_volume() is None
    assert await p.get_statistics() is None
    assert await p.get_limit_up() is None


@pytest.mark.asyncio
async def test_stub_indices():
    p = _StubProvider()
    r = await p.get_indices()
    assert r is not None
    assert r["sh"].name == "上证指数"
    assert r["sh"].change == 0.0123


def test_factory_tickflow_only():
    tf = _StubProvider()
    tf.name = "tickflow"
    chain = build_provider_chain("indices", {"tickflow": tf}, mode="tickflow")
    assert len(chain) == 1
    assert chain[0].name == "tickflow"


def test_factory_mixed_chain_order():
    """mixed 模式：TickFlow 主源在前，legacy fallback 在后。"""
    tf = _StubProvider()
    tf.name = "tickflow"
    legacy = _StubProvider()
    legacy.name = "legacy"
    chain = build_provider_chain(
        "indices", {"tickflow": tf, "legacy": legacy}, mode="mixed"
    )
    assert [p.name for p in chain] == ["tickflow", "legacy"]


def test_factory_missing_provider_returns_empty():
    assert build_provider_chain("indices", {}, mode="mixed") == []
    assert build_provider_chain("indices", {}, mode="tickflow") == []


def test_factory_tickflow_mode_ignores_legacy():
    """tickflow 模式下即使有 legacy 也不用（纯 TickFlow）。"""
    tf = _StubProvider()
    tf.name = "tickflow"
    legacy = _StubProvider()
    legacy.name = "legacy"
    chain = build_provider_chain(
        "volume", {"tickflow": tf, "legacy": legacy}, mode="tickflow"
    )
    assert [p.name for p in chain] == ["tickflow"]
