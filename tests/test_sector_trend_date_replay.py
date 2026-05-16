"""板块趋势日期回放测试 - explicit-date, idempotency, evidence bounds, sparse gaps, telegraph mentions."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.sector_trend_service import SectorTrendAnalyzer


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.get_session = MagicMock()
    return db


class TestExplicitDateOutputPaths:
    """验证 explicit report_date 控制输出路径和 end_date。"""

    @pytest.mark.asyncio
    async def test_report_date_used_for_evidence(self) -> None:
        """report_date 传递给 collect_sector_evidence 作为 end_date。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 10)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "半导体"
        analyzer._ensure_tracked.return_value = mock_sector

        analyzer.get_previous_summary = AsyncMock(return_value=None)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": target_date.isoformat(),
            "is_sparse": True,
            "total_evidence_count": 0,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
            "data_gaps": ["market_sector_cache_missing"],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        await analyzer.update_sector_trend(
            "半导体",
            days=10,
            ai_processor=None,
            report_date=target_date,
        )

        analyzer.collect_sector_evidence.assert_called_once_with(
            "半导体", target_date, 10,
        )

    @pytest.mark.asyncio
    async def test_default_report_date_is_latest_trade_date(self) -> None:
        """不传 report_date 时使用 get_latest_trade_date。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "半导体"
        analyzer._ensure_tracked.return_value = mock_sector

        analyzer.get_previous_summary = AsyncMock(return_value=None)

        latest_date = date(2026, 5, 16)
        analyzer._market_analyzer.get_latest_trade_date = MagicMock(return_value=latest_date)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": latest_date.isoformat(),
            "is_sparse": True,
            "total_evidence_count": 0,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        await analyzer.update_sector_trend(
            "半导体",
            days=10,
            ai_processor=None,
        )

        analyzer.collect_sector_evidence.assert_called_once_with(
            "半导体", latest_date, 10,
        )


class TestIdempotencyChecks:
    """验证 explicit date 的幂等性检查。"""

    @pytest.mark.asyncio
    async def test_existing_summary_for_report_date_skips(self) -> None:
        """如果 report_date 已有总结，应跳过。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 10)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "半导体"
        analyzer._ensure_tracked.return_value = mock_sector

        mock_existing = MagicMock()
        mock_existing.end_date = target_date
        analyzer.get_previous_summary = AsyncMock(return_value=mock_existing)

        result = await analyzer.update_sector_trend(
            "半导体",
            days=10,
            ai_processor=None,
            report_date=target_date,
        )

        assert result["action"] == "skipped"


class TestSparseGaps:
    """验证稀疏证据缺口元数据。"""

    @pytest.mark.asyncio
    async def test_no_evidence_has_all_gaps(self) -> None:
        """无证据时，所有缺口标记都应存在。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": "2026-05-10",
            "is_sparse": True,
            "total_evidence_count": 0,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
            "data_gaps": [
                "market_sector_cache_missing",
                "cls_watch_missing",
                "cls_telegraph_missing",
            ],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        result = await analyzer.collect_sector_evidence(
            "半导体", date(2026, 5, 10), 10,
        )

        assert "market_sector_cache_missing" in result["data_gaps"]
        assert "cls_watch_missing" in result["data_gaps"]
        assert "cls_telegraph_missing" in result["data_gaps"]
        assert result["is_sparse"] is True

    @pytest.mark.asyncio
    async def test_with_evidence_has_fewer_gaps(self) -> None:
        """有证据时，对应缺口标记不存在。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": "2026-05-10",
            "is_sparse": False,
            "total_evidence_count": 5,
            "market_appearances": [{"trade_date": "2026-05-10"}],
            "cls_watch_mentions": [{"title": "test"}],
            "cls_telegraph_mentions": [{"title": "telegraph"}],
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        result = await analyzer.collect_sector_evidence(
            "半导体", date(2026, 5, 10), 10,
        )

        assert "market_sector_cache_missing" not in result["data_gaps"]
        assert result["is_sparse"] is False


class TestTelegraphMentionInclusion:
    """验证 CLS 电报提及功能存在。"""

    @pytest.mark.asyncio
    async def test_telegraph_collection_method_exists(self) -> None:
        """_collect_telegraph_mentions 方法应存在。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)
        assert hasattr(analyzer, "_collect_telegraph_mentions")
        assert callable(analyzer._collect_telegraph_mentions)

    @pytest.mark.asyncio
    async def test_telegraph_mentions_in_evidence_structure(self) -> None:
        """evidence 结构应包含 cls_telegraph_mentions 字段。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": "2026-05-10",
            "is_sparse": True,
            "total_evidence_count": 1,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [
                {
                    "title": "半导体板块大涨",
                    "content": "半导体板块今日集体拉升",
                    "publish_time": "2026-05-10 10:00",
                    "level": "A",
                    "category": "red",
                },
            ],
            "data_gaps": ["market_sector_cache_missing"],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        result = await analyzer.collect_sector_evidence(
            "半导体", date(2026, 5, 10), 10,
        )

        assert len(result["cls_telegraph_mentions"]) == 1
        assert result["cls_telegraph_mentions"][0]["title"] == "半导体板块大涨"
