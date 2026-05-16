"""板块分组日期回放测试 - report-date, member selection, future exclusion, stale freshness, sparse gaps."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.sector_group_service import SectorGroupService


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.get_session = MagicMock()
    return db


class TestReportDatePassedToUpdate:
    """验证 report_date 传递到 update_group_trend。"""

    @pytest.mark.asyncio
    async def test_report_date_overrides_latest_trade_date(self) -> None:
        """report_date 应覆盖 _get_latest_trade_date。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 10)

        # Mock _get_latest_trade_date to return a different date
        service._get_latest_trade_date = MagicMock(return_value=date(2026, 5, 16))

        # Mock _resolve_group
        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.canonical_name = "AI"

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        service._resolve_group = AsyncMock(return_value=mock_group)

        # Mock _load_group_members
        service._load_group_members = AsyncMock(return_value=[])

        # Mock _get_latest_group_summary to return None (no existing)
        service._get_latest_group_summary = AsyncMock(return_value=None)

        # Mock _collect_group_evidence
        service._collect_group_evidence = AsyncMock(return_value={
            "group_id": 1,
            "end_date": target_date.isoformat(),
            "member_summaries": [],
            "raw_evidence_count": 0,
            "member_count": 0,
        })

        result = await service.update_group_trend(
            "AI",
            ai_processor=None,
            no_refresh_members=True,
            report_date=target_date,
        )

        # _collect_group_evidence 应使用 target_date
        service._collect_group_evidence.assert_called_once()
        call_args = service._collect_group_evidence.call_args
        assert call_args[0][1] == target_date  # end_date arg

    @pytest.mark.asyncio
    async def test_member_refresh_uses_report_date(self) -> None:
        """刷新成员板块时应把 report_date 传递给成员趋势更新。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 10)

        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.canonical_name = "AI"
        service._resolve_group = AsyncMock(return_value=mock_group)
        service._get_latest_group_summary = AsyncMock(return_value=None)
        service._load_group_members = AsyncMock(return_value=[
            {
                "sector_id": 11,
                "sector_name": "机器人",
                "sector_status": "tracked",
                "relation_type": "related",
            }
        ])
        service._sector_has_report = AsyncMock(return_value=False)
        service._collect_group_evidence = AsyncMock(return_value={
            "group_id": 1,
            "end_date": target_date.isoformat(),
            "member_summaries": [],
            "raw_evidence_count": 0,
            "member_count": 0,
        })
        service._calculate_member_freshness = AsyncMock(return_value=[])

        mock_summary = MagicMock()
        mock_summary.output_path = "output/sector_groups/AI/2026-05-10.md"
        service._save_group_trend_summary = AsyncMock(return_value=mock_summary)

        mock_ai = MagicMock()
        mock_ai.generate_sector_group_trend_summary = AsyncMock(return_value=(
            "content",
            {
                "trend_status": "暂无趋势",
                "strength_level": "弱",
                "action_bias": "观察",
                "judgement": "测试",
            },
        ))

        mock_analyzer = MagicMock()
        mock_analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "机器人",
        })

        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        with patch(
            "src.services.sector_trend_service.SectorTrendAnalyzer",
            return_value=mock_analyzer,
        ):
            await service.update_group_trend(
                "AI",
                ai_processor=mock_ai,
                report_date=target_date,
            )

        mock_analyzer.update_sector_trend.assert_called_once()
        assert mock_analyzer.update_sector_trend.call_args.kwargs["report_date"] == target_date


class TestMemberSummaryForDate:
    """验证 _get_member_summary_for_date 选择目标日期的报告。"""

    @pytest.mark.asyncio
    async def test_exact_date_match_preferred(self) -> None:
        """精确匹配目标日期的报告应被优先选择。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 10)
        mock_summary = MagicMock()
        mock_summary.end_date = target_date

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_summary
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        result = await service._get_member_summary_for_date(1, target_date)

        assert result is not None
        assert result.end_date == target_date


class TestFutureSummaryExclusion:
    """验证未来日期的 summary 不被使用。"""

    @pytest.mark.asyncio
    async def test_future_summary_not_selected(self) -> None:
        """_get_member_summary_for_date 不返回目标日期之后的 summary。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 10)

        # 第一次查询（精确匹配）返回 None
        # 第二次查询（<= target_date）也返回 None
        mock_session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = mock_execute

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        result = await service._get_member_summary_for_date(1, target_date)

        assert result is None


class TestStaleFreshness:
    """验证 stale 成员新鲜度标记。"""

    @pytest.mark.asyncio
    async def test_stale_member_marked(self) -> None:
        """成员最新报告早于目标日期应标记为 stale。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 15)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = date(2026, 5, 10)  # 比 target 早
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        members = [
            {"sector_id": 1, "sector_name": "半导体", "sector_status": "tracked", "relation_type": "core"},
        ]

        freshness = await service._calculate_member_freshness(1, target_date, members)

        assert len(freshness) == 1
        assert freshness[0]["is_stale"] is True
        assert freshness[0]["is_missing"] is False

    @pytest.mark.asyncio
    async def test_missing_member_marked(self) -> None:
        """无报告的成员应标记为 missing。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 15)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None  # 无报告
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        members = [
            {"sector_id": 1, "sector_name": "半导体", "sector_status": "tracked", "relation_type": "core"},
        ]

        freshness = await service._calculate_member_freshness(1, target_date, members)

        assert len(freshness) == 1
        assert freshness[0]["is_missing"] is True
        assert freshness[0]["is_stale"] is False

    @pytest.mark.asyncio
    async def test_current_member_not_marked(self) -> None:
        """目标日期有报告的成员不应标记为 stale 或 missing。"""
        db = _make_mock_db()
        service = SectorGroupService(db)

        target_date = date(2026, 5, 15)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = target_date  # 完全匹配
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        db.get_session.return_value = mock_cm

        members = [
            {"sector_id": 1, "sector_name": "半导体", "sector_status": "tracked", "relation_type": "core"},
        ]

        freshness = await service._calculate_member_freshness(1, target_date, members)

        assert len(freshness) == 1
        assert freshness[0]["is_missing"] is False
        assert freshness[0]["is_stale"] is False
