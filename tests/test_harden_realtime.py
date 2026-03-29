"""Tests for harden-realtime-market-data-fetching change."""

import hashlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.finance import FinanceClient
from src.services.market_data_cache_service import MarketDataCacheService, _derive_sector_code


# ========== Test 1: Snapshot reuse ==========


@pytest.mark.asyncio
async def test_get_all_market_data_shares_snapshot():
    """get_all_market_data should fetch snapshot once and share it."""
    client = FinanceClient()

    mock_stocks = [
        {"f12": "600000", "f3": 5.0, "f6": 5_000_000_000},
        {"f12": "000001", "f3": -2.0, "f6": 3_000_000_000},
    ]

    with patch.object(client, "_fetch_stock_snapshot", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (
            mock_stocks,
            {"status": "ok", "source": "eastmoney_curl", "actual_count": len(mock_stocks), "expected_count": len(mock_stocks)},
        )

        with patch.object(client, "get_index_data", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = {"sh": {"name": "上证指数", "close": 3000, "change": 0.01}}

            with patch.object(client, "get_sector_data", new_callable=AsyncMock) as mock_sector:
                mock_sector.return_value = {"top_sectors": [], "bottom_sectors": []}

                with patch.object(client, "get_limit_up_stocks", new_callable=AsyncMock) as mock_limit:
                    mock_limit.return_value = []

                    result = await client.get_all_market_data()

    # _fetch_stock_snapshot should be called exactly once
    mock_fetch.assert_awaited_once()
    assert result["volume"]["total_volume"] > 0
    assert result["statistics"]["up_count"] == 1
    assert result["statistics"]["down_count"] == 1


@pytest.mark.asyncio
async def test_get_volume_data_accepts_stocks_param():
    """get_volume_data should use passed stocks instead of fetching new ones."""
    client = FinanceClient()

    stocks = [
        {"f12": "600000", "f6": 300000},
        {"f12": "000001", "f6": 500000},
    ]

    result = client.compute_volume_data(stocks)
    assert result["total_volume"] > 0


@pytest.mark.asyncio
async def test_get_statistics_accepts_stocks_param():
    """get_statistics should use passed stocks instead of fetching new ones."""
    client = FinanceClient()

    stocks = [
        {"f12": "600000", "f3": 5.0},
        {"f12": "000001", "f3": -2.0},
        {"f12": "300001", "f3": 0.0},
    ]

    result = client.compute_statistics(stocks)
    assert result["up_count"] == 1
    assert result["down_count"] == 1
    assert result["flat_count"] == 1


# ========== Test 2: Trade date parameter ==========


def test_get_limit_up_stocks_accepts_trade_date():
    """get_limit_up_stocks signature should accept trade_date parameter."""
    import inspect
    sig = inspect.signature(FinanceClient.get_limit_up_stocks)
    params = list(sig.parameters.keys())
    assert "trade_date" in params


@pytest.mark.asyncio
async def test_get_limit_up_stocks_default_trade_date():
    """get_limit_up_stocks should work with default trade_date=None."""
    client = FinanceClient()
    with patch.object(client, "_retry_request", new_callable=AsyncMock):
        with patch.object(client._eastmoney, "get_stock_list", return_value=None):
            result = await client.get_limit_up_stocks()
            assert isinstance(result, list)


# ========== Test 3: Sector stable code ==========


def test_derive_sector_code_with_existing_code():
    """Should use existing code if available."""
    data = {"code": "BK123", "name": "新能源"}
    assert _derive_sector_code(data) == "BK123"


def test_derive_sector_code_from_name():
    """Should derive stable code from name when code is empty."""
    data = {"code": "", "name": "新能源"}
    result = _derive_sector_code(data)
    assert result.startswith("S_")
    # Same name should produce same code
    assert _derive_sector_code({"code": "", "name": "新能源"}) == result


def test_derive_sector_code_empty_name():
    """Should produce a fallback code for empty name."""
    data = {"code": "", "name": ""}
    result = _derive_sector_code(data)
    assert result.startswith("SECTOR_")


def test_derive_sector_code_deterministic():
    """Same name should always produce same code."""
    name = "人工智能"
    code1 = _derive_sector_code({"code": "", "name": name})
    code2 = _derive_sector_code({"code": "", "name": name})
    assert code1 == code2


# ========== Test 4: Sector cache save/load round-trip ==========


@pytest.mark.asyncio
async def test_sector_cache_round_trip(integration_db):
    """Sector data should survive a save/load cycle with stable codes."""
    service = MarketDataCacheService(integration_db)

    trade_date = date(2026, 3, 27)
    market_data = {
        "indices": {},
        "volume": {"sh_volume": 100, "sz_volume": 200, "total_volume": 300},
        "statistics": {"up_count": 10, "down_count": 5, "flat_count": 3},
        "sectors": {
            "top_sectors": [
                {"name": "新能源", "code": "BK001", "change": 0.05},
                {"name": "人工智能", "code": "BK002", "change": 0.03},
            ],
            "bottom_sectors": [
                {"name": "房地产", "code": "", "change": -0.04},
            ],
        },
        "limit_up": [],
    }

    await service.save_market_data(trade_date, market_data)

    cached = await service.get_cached(trade_date)
    assert cached is not None

    # All sectors should have stable codes
    all_cached_sectors = cached["sectors"]["top_sectors"] + cached["sectors"]["bottom_sectors"]
    for sector in all_cached_sectors:
        assert sector.get("code", "") != "", f"Sector {sector.get('name')} has empty code"

    # Named sectors should match
    top_names = {s["name"] for s in cached["sectors"]["top_sectors"]}
    assert "新能源" in top_names
    assert "人工智能" in top_names


@pytest.mark.asyncio
async def test_sector_no_unique_constraint_violation(integration_db):
    """Multiple sectors without explicit code should not cause unique constraint errors."""
    service = MarketDataCacheService(integration_db)

    trade_date = date(2026, 3, 27)

    # Save sectors with empty codes (akshare fallback scenario)
    market_data = {
        "indices": {},
        "volume": {},
        "statistics": {},
        "sectors": {
            "top_sectors": [
                {"name": "板块A", "code": "", "change": 0.05},
                {"name": "板块B", "code": "", "change": 0.03},
                {"name": "板块C", "code": "", "change": 0.02},
                {"name": "板块D", "code": "", "change": 0.01},
                {"name": "板块E", "code": "", "change": 0.01},
            ],
            "bottom_sectors": [],
        },
        "limit_up": [],
    }

    # Should not raise IntegrityError
    await service.save_market_data(trade_date, market_data)

    cached = await service.get_cached(trade_date)
    assert cached is not None
    assert len(cached["sectors"]["top_sectors"]) == 5

    # Each sector should have a unique derived code
    codes = [s["code"] for s in cached["sectors"]["top_sectors"]]
    assert len(set(codes)) == 5, f"Duplicate codes found: {codes}"
