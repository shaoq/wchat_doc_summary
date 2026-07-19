"""盘后日K管道单测（_normalize 纯逻辑 + mock client 的 sync 流程）。"""

from contextlib import asynccontextmanager
from datetime import date

import pytest

from src.services import market_data_sync_service as svc
from src.services.market_data_sync_service import MarketDataSyncService


# ---- _normalize / _ms_to_date 纯逻辑 ----

def test_ms_to_date():
    # ts=0 → 1970-01-01 08:00 CST → date 1970-01-01
    assert svc._ms_to_date(0) == date(1970, 1, 1)
    # +1 天（86400000 ms）
    assert svc._ms_to_date(86400000) == date(1970, 1, 2)


def test_idx_safe():
    assert svc._idx([1.0, 2.0], 0) == 1.0
    assert svc._idx([1.0], 5) is None
    assert svc._idx(None, 0) is None


def test_normalize_change_pct_computed():
    """两根 K：第0根 change_pct=None（无前值），第1根=(close1-close0)/close0。"""
    batch = {
        "600000.SH": {
            "timestamp": [0, 86400000],
            "open": [8.92, 8.85],
            "high": [8.94, 8.97],
            "low": [8.8, 8.82],
            "close": [8.85, 8.87],
            "volume": [755826, 796240],
            "amount": [6.7e8, 7e8],
        }
    }
    rows = MarketDataSyncService._normalize(batch)
    assert len(rows) == 2
    assert rows[0]["change_pct"] is None  # 第0根无前值
    expected = (8.87 - 8.85) / 8.85
    assert rows[1]["change_pct"] == pytest.approx(expected, rel=1e-6)
    assert rows[1]["trade_date"] == date(1970, 1, 2)
    assert rows[1]["symbol"] == "600000.SH"


def test_normalize_empty_and_garbage():
    assert MarketDataSyncService._normalize({}) == []
    assert MarketDataSyncService._normalize({"X": None}) == []
    assert MarketDataSyncService._normalize({"X": {"timestamp": []}}) == []


# ---- sync 流程（mock client，不触网）----

class _FakeExchanges:
    @staticmethod
    def get_instruments(ex, instrument_type=None):  # noqa: ARG004
        # 按 ex 区分，模拟 SH/SZ/BJ 分别返回
        if ex == "SH":
            return [{"symbol": "600000.SH"}, {"symbol": "000001.SZ"}]
        return []


class _FakeKlines:
    @staticmethod
    def batch(symbols, **kw):  # noqa: ARG004
        return {
            "600000.SH": {
                "timestamp": [0, 86400000],
                "open": [8.92, 8.85], "high": [8.94, 8.97], "low": [8.8, 8.82],
                "close": [8.85, 8.87], "volume": [755826, 796240],
                "amount": [6.7e8, 7e8],
            }
        }


class _FakeTF:
    exchanges = _FakeExchanges
    klines = _FakeKlines


class _FakeDB:
    @asynccontextmanager
    async def get_session(self):
        class _S:
            async def execute(self, stmt):  # noqa: ARG002
                pass

        yield _S()


@pytest.mark.asyncio
async def test_sync_calls_fetch_and_returns_counts(monkeypatch):
    """sync 调 _fetch_all_symbols + _fetch_daily_klines，返回计数。"""
    monkeypatch.setattr(svc, "get_client", lambda: _FakeTF())

    written: list[list[dict]] = []

    class _Repo:
        async def upsert_rows(self, rows):
            written.append(rows)
            return len(rows)

    service = MarketDataSyncService(_FakeDB())
    service.repo = _Repo()  # type: ignore[assignment]

    result = await service.sync(count=1)
    assert result["symbols"] == 2  # 仅 SH 返回 2 只
    # 拉 count+1=2 根 → 600000.SH 的 2 行（mock 只返回 600000.SH）
    assert result["rows"] == len(written[0])
    assert len(written[0]) == 2
