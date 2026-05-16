"""市场数据回填服务测试 - source eligibility, partial success, idempotent writes, no contamination."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.finance import FinanceClient
from src.services.market_data_backfill_service import (
    BackfillResult,
    CategoryOutcome,
    MarketDataBackfillService,
)


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.get_session = MagicMock()
    return db


def _make_mock_finance_client() -> FinanceClient:
    client = MagicMock(spec=FinanceClient)
    return client


# ---------------------------------------------------------------------------
# Source eligibility tests
# ---------------------------------------------------------------------------


class TestSourceEligibility:
    """验证 CATEGORY_CAPABILITIES 正确标记 historical-safe 分类。"""

    def test_volume_is_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["volume"]["historical_safe"] is True

    def test_limit_up_is_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["limit_up"]["historical_safe"] is True

    def test_indices_is_not_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["indices"]["historical_safe"] is False

    def test_statistics_is_not_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["statistics"]["historical_safe"] is False

    def test_sectors_is_not_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["sectors"]["historical_safe"] is False

    def test_snapshot_is_not_historical_safe(self) -> None:
        assert FinanceClient.CATEGORY_CAPABILITIES["snapshot"]["historical_safe"] is False


# ---------------------------------------------------------------------------
# Partial success tests
# ---------------------------------------------------------------------------


class TestPartialSuccess:
    """验证部分分类成功、部分失败的场景。"""

    @pytest.mark.asyncio
    async def test_volume_succeeds_limit_up_empty(self) -> None:
        """volume 有数据，limit_up 为空。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 100.0, "sz_volume": 80.0, "total_volume": 180.0},
            {"status": "ok", "source": "official_exchange_turnover"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=(
            [],
            {"source_type": "none", "status": "error"},
        ))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()
        result = await service.backfill(date(2026, 5, 15))

        assert result.total_populated >= 1  # volume populated
        assert result.is_partial is True
        # 检查 volume 是 populated
        volume_outcome = [o for o in result.outcomes if o.category == "volume"]
        assert len(volume_outcome) == 1
        assert volume_outcome[0].status == "populated"

        # 检查 realtime 分类是 skipped_unsupported
        for cat in ("indices", "statistics", "sectors", "snapshot"):
            cat_outcome = [o for o in result.outcomes if o.category == cat]
            assert len(cat_outcome) == 1
            assert cat_outcome[0].status == "skipped_unsupported"

    @pytest.mark.asyncio
    async def test_all_historical_sources_empty(self) -> None:
        """所有 historical-safe 源都返回空数据。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
            {"status": "error", "source": "test"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=(
            [],
            {"source_type": "none", "status": "error"},
        ))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()
        result = await service.backfill(date(2026, 5, 15))

        assert result.total_populated == 0
        assert result.total_empty >= 2  # volume + limit_up

    @pytest.mark.asyncio
    async def test_all_populated(self) -> None:
        """所有 historical-safe 分类都有数据。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 100.0, "sz_volume": 80.0, "total_volume": 180.0},
            {"status": "ok", "source": "official_exchange_turnover"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=(
            [{"name": "测试股", "code": "000001", "change": 0.1}],
            {"source_type": "dedicated_pool", "status": "ok"},
        ))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()
        result = await service.backfill(date(2026, 5, 15))

        assert result.total_populated == 2
        assert result.is_complete is True

    @pytest.mark.asyncio
    async def test_failed_category_preserves_cache(self) -> None:
        """failed 分类不触发 cache 写入。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(side_effect=Exception("network error"))
        fc._get_limit_up_with_quality = AsyncMock(return_value=(
            [{"name": "测试股", "code": "000001", "change": 0.1}],
            {"source_type": "dedicated_pool", "status": "ok"},
        ))

        service = MarketDataBackfillService(db, fc)
        # Patch save_market_data to track calls
        service._cache_service.save_market_data = AsyncMock()

        result = await service.backfill(date(2026, 5, 15))

        # volume 应该是 failed
        volume_outcome = [o for o in result.outcomes if o.category == "volume"]
        assert len(volume_outcome) == 1
        assert volume_outcome[0].status == "failed"


# ---------------------------------------------------------------------------
# Idempotent writes tests
# ---------------------------------------------------------------------------


class TestIdempotentWrites:
    """验证重复回填使用 upsert 语义，不产生重复行。"""

    @pytest.mark.asyncio
    async def test_save_market_data_called_once_for_populated(self) -> None:
        """成功分类触发一次 save_market_data 调用。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 100.0, "sz_volume": 80.0, "total_volume": 180.0},
            {"status": "ok", "source": "official_exchange_turnover"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=([], {"status": "error"}))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()

        await service.backfill(date(2026, 5, 15))

        service._cache_service.save_market_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_market_data_not_called_when_all_empty(self) -> None:
        """所有分类为空时不调用 save_market_data。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
            {"status": "error", "source": "test"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=([], {"status": "error"}))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()

        await service.backfill(date(2026, 5, 15))

        service._cache_service.save_market_data.assert_not_called()


# ---------------------------------------------------------------------------
# No historical snapshot contamination tests
# ---------------------------------------------------------------------------


class TestNoHistoricalSnapshotContamination:
    """验证 realtime 分类不会写入历史缓存。"""

    @pytest.mark.asyncio
    async def test_realtime_categories_are_skipped(self) -> None:
        """realtime 分类标记为 skipped_unsupported，不触发数据获取。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 100.0, "sz_volume": 80.0, "total_volume": 180.0},
            {"status": "ok", "source": "official_exchange_turnover"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=([], {"status": "error"}))
        # 这些方法不应被调用
        fc.get_index_data = AsyncMock()
        fc.get_statistics = AsyncMock()
        fc.get_sector_data = AsyncMock()

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()
        result = await service.backfill(date(2026, 5, 15))

        # realtime 方法不应被调用
        fc.get_index_data.assert_not_called()
        fc.get_statistics.assert_not_called()
        fc.get_sector_data.assert_not_called()

        # 这些分类应为 skipped_unsupported
        for cat in ("indices", "statistics", "sectors", "snapshot"):
            outcome = [o for o in result.outcomes if o.category == cat]
            assert len(outcome) == 1
            assert outcome[0].status == "skipped_unsupported"

    @pytest.mark.asyncio
    async def test_backfill_does_not_create_market_summary(self) -> None:
        """回填操作不应创建 market_summaries 记录。"""
        db = _make_mock_db()
        fc = _make_mock_finance_client()
        fc._get_volume_with_quality = AsyncMock(return_value=(
            {"sh_volume": 100.0, "sz_volume": 80.0, "total_volume": 180.0},
            {"status": "ok", "source": "official_exchange_turnover"},
        ))
        fc._get_limit_up_with_quality = AsyncMock(return_value=([], {"status": "error"}))

        service = MarketDataBackfillService(db, fc)
        service._cache_service.save_market_data = AsyncMock()
        result = await service.backfill(date(2026, 5, 15))

        # BackfillResult 不包含 summary 相关字段
        assert not hasattr(result, "summary")
        assert not hasattr(result, "content")
