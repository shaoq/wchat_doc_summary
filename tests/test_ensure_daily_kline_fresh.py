"""task 11: _ensure_daily_kline_fresh 自动 sync 单测。"""

from datetime import timedelta

import pytest

from src.api.finance import FinanceClient
from src.services import trade_calendar


@pytest.mark.asyncio
async def test_skips_sync_when_daily_kline_fresh(monkeypatch):
    """daily_kline.latest_date >= 最新交易日 → 不 sync。"""
    target = trade_calendar.get_effective_fetch_trade_date()

    async def mock_latest(self):  # noqa: ARG001
        return target

    monkeypatch.setattr(
        "src.storage.daily_kline_repository.DailyKlineRepository.latest_date", mock_latest
    )

    synced: list[int] = []

    async def mock_sync(self, count=1):  # noqa: ARG001
        synced.append(count)
        return {"rows": 0}

    monkeypatch.setattr(
        "src.services.market_data_sync_service.MarketDataSyncService.sync", mock_sync
    )

    fc = FinanceClient()
    await fc._ensure_daily_kline_fresh(db=object())
    assert synced == []  # 已最新，不 sync


@pytest.mark.asyncio
async def test_syncs_when_daily_kline_stale(monkeypatch):
    """daily_kline.latest_date < 最新交易日 → 自动 sync(count=1)。"""
    target = trade_calendar.get_effective_fetch_trade_date()
    stale = target - timedelta(days=5)

    async def mock_latest(self):  # noqa: ARG001
        return stale

    monkeypatch.setattr(
        "src.storage.daily_kline_repository.DailyKlineRepository.latest_date", mock_latest
    )

    synced: list[int] = []

    async def mock_sync(self, count=1):
        synced.append(count)
        return {"rows": 100}

    monkeypatch.setattr(
        "src.services.market_data_sync_service.MarketDataSyncService.sync", mock_sync
    )

    fc = FinanceClient()
    await fc._ensure_daily_kline_fresh(db=object())
    assert synced == [1]  # 落后，触发 sync


@pytest.mark.asyncio
async def test_syncs_when_daily_kline_empty(monkeypatch):
    """daily_kline 空（latest=None）→ 自动 sync。"""
    async def mock_latest(self):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        "src.storage.daily_kline_repository.DailyKlineRepository.latest_date", mock_latest
    )

    synced: list[int] = []

    async def mock_sync(self, count=1):
        synced.append(count)
        return {"rows": 11000}

    monkeypatch.setattr(
        "src.services.market_data_sync_service.MarketDataSyncService.sync", mock_sync
    )

    fc = FinanceClient()
    await fc._ensure_daily_kline_fresh(db=object())
    assert synced == [1]
