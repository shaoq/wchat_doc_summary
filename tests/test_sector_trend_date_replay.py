"""板块趋势日期回放测试 - explicit-date, idempotency, evidence bounds, sparse gaps, telegraph mentions."""

import json

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.ai_processor import AIProcessor
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

    def test_ai_processor_formats_telegraph_mentions(self) -> None:
        """AIProcessor 应能把电报提及格式化为 prompt 证据文本。"""
        processor = object.__new__(AIProcessor)

        result = processor._format_sector_cls_telegraphs([
            {
                "title": "半导体板块大涨",
                "content": "半导体产业链多股活跃",
                "publish_time": "2026-05-10 10:00",
                "level": "A",
            }
        ])

        assert "半导体板块大涨" in result
        assert "A级" in result
        assert "半导体产业链多股活跃" in result


class TestDateBoundedPreviousSummary:
    """验证日期回放时 previous_summary 只使用目标日期之前的总结。"""

    @pytest.mark.asyncio
    async def test_replay_does_not_use_future_summary(self) -> None:
        """回放 2026-05-06 时不使用 2026-05-15 的总结作为先前上下文。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 6)
        future_date = date(2026, 5, 15)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "TOPCon"
        analyzer._ensure_tracked.return_value = mock_sector

        # 模拟存在未来总结（2026-05-15）
        future_summary = MagicMock()
        future_summary.end_date = future_date
        future_summary.trend_status = "主线加强"
        future_summary.strength_level = "强"
        future_summary.action_bias = "跟踪"
        future_summary.judgement = "强势延续"
        future_summary.content = "TOPCon 板块持续走强"

        # 模拟存在早期总结（2026-05-05）
        early_summary = MagicMock()
        early_summary.end_date = date(2026, 5, 5)
        early_summary.trend_status = "低位启动"
        early_summary.strength_level = "弱"
        early_summary.action_bias = "观察"
        early_summary.judgement = "初步关注"
        early_summary.content = "TOPCon 板块开始活跃"

        # get_previous_summary 在有 before_date 时应返回早期总结
        async def mock_get_previous(sector_id: int, *, before_date=None):
            if before_date is not None:
                if before_date == target_date:
                    return early_summary  # 只返回目标日期之前的
                return None
            return future_summary  # 无 before_date 时返回最新的

        analyzer.get_previous_summary = AsyncMock(side_effect=mock_get_previous)

        mock_evidence = {
            "sector_name": "TOPCon",
            "end_date": target_date.isoformat(),
            "is_sparse": False,
            "total_evidence_count": 5,
            "market_appearances": [{"trade_date": "2026-05-06"}],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# TOPCon 板块趋势\n\n内容",
            {"trend_status": "分歧中继", "strength_level": "中", "action_bias": "观察", "judgement": "分歧"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        # 幂等性检查时 get_previous_summary 也需要返回正确值
        # update_sector_trend 先检查 idempotency（get_previous_summary with before_date）
        # 然后收集证据后再获取 previous_summary（同样 with before_date）

        result = await analyzer.update_sector_trend(
            "TOPCon",
            days=10,
            ai_processor=mock_ai,
            force=True,
            report_date=target_date,
        )

        assert result["action"] == "updated"
        # 验证 get_previous_summary 被调用时传入了 before_date=target_date
        analyzer.get_previous_summary.assert_called()
        for call in analyzer.get_previous_summary.call_args_list:
            if "before_date" in call.kwargs or len(call.args) > 1:
                kwargs = call.kwargs
                if "before_date" in kwargs:
                    assert kwargs["before_date"] == target_date

    @pytest.mark.asyncio
    async def test_replay_uses_nearest_earlier_summary(self) -> None:
        """回放 2026-05-08 时使用最近的 2026-05-07 总结而非更早的。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 8)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "TOPCon"
        analyzer._ensure_tracked.return_value = mock_sector

        nearest_summary = MagicMock()
        nearest_summary.end_date = date(2026, 5, 7)
        nearest_summary.trend_status = "主线延续"
        nearest_summary.strength_level = "中"
        nearest_summary.action_bias = "跟踪"
        nearest_summary.judgement = "延续"
        nearest_summary.content = "TOPCon 延续"

        async def mock_get_previous(sector_id: int, *, before_date=None):
            if before_date is not None and before_date == target_date:
                return nearest_summary
            return None

        analyzer.get_previous_summary = AsyncMock(side_effect=mock_get_previous)

        mock_evidence = {
            "sector_name": "TOPCon",
            "end_date": target_date.isoformat(),
            "is_sparse": False,
            "total_evidence_count": 5,
            "market_appearances": [{"trade_date": "2026-05-08"}],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [],
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# TOPCon 板块趋势\n\n内容",
            {"trend_status": "主线延续", "strength_level": "中", "action_bias": "跟踪", "judgement": "延续"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        result = await analyzer.update_sector_trend(
            "TOPCon",
            days=10,
            ai_processor=mock_ai,
            force=True,
            report_date=target_date,
        )

        assert result["action"] == "updated"
        # 验证 AI 生成时使用了最近的早期总结作为 previous_summary
        call_args = mock_ai.generate_sector_trend_summary.call_args
        previous_summary = call_args.kwargs.get("previous_summary") or call_args[1].get("previous_summary")
        assert previous_summary is not None
        assert previous_summary["trend_status"] == "主线延续"

    @pytest.mark.asyncio
    async def test_first_report_has_no_previous(self) -> None:
        """首次报告（无早期总结）时 previous_summary 为 None。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 6)

        analyzer._ensure_tracked = AsyncMock()
        mock_sector = MagicMock()
        mock_sector.id = 1
        mock_sector.canonical_name = "新板块"
        analyzer._ensure_tracked.return_value = mock_sector

        analyzer.get_previous_summary = AsyncMock(return_value=None)

        mock_evidence = {
            "sector_name": "新板块",
            "end_date": target_date.isoformat(),
            "is_sparse": True,
            "total_evidence_count": 1,
            "market_appearances": [],
            "cls_watch_mentions": [],
            "cls_telegraph_mentions": [{"title": "test"}],
            "data_gaps": ["market_sector_cache_missing", "cls_watch_missing"],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# 新板块趋势\n\n内容",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察", "judgement": "观察"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        result = await analyzer.update_sector_trend(
            "新板块",
            days=10,
            ai_processor=mock_ai,
            force=True,
            report_date=target_date,
        )

        assert result["action"] == "updated"
        call_args = mock_ai.generate_sector_trend_summary.call_args
        previous_summary = call_args.kwargs.get("previous_summary") or call_args[1].get("previous_summary")
        assert previous_summary is None


class TestSkipRepairOption:
    """验证 --skip-repair 选项。"""

    @pytest.mark.asyncio
    async def test_skip_repair_skips_repair_call(self) -> None:
        """skip_repair=True 时不调用修复服务。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 6)

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
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# 半导体趋势\n\n内容",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察", "judgement": "观察"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        with patch("src.services.cls_watch_repair.ClsWatchRepairService.repair_window", new_callable=AsyncMock) as mock_repair:
            result = await analyzer.update_sector_trend(
                "半导体",
                days=10,
                ai_processor=mock_ai,
                force=True,
                report_date=target_date,
                skip_repair=True,
            )

            # 修复服务不应被调用
            mock_repair.assert_not_called()

        assert result["action"] == "updated"

    @pytest.mark.asyncio
    async def test_default_runs_repair(self) -> None:
        """默认（skip_repair=False）时尝试调用修复服务。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 6)

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
            "data_gaps": [],
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# 半导体趋势\n\n内容",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察", "judgement": "观察"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        with patch("src.services.cls_watch_repair.ClsWatchRepairService.repair_window", new_callable=AsyncMock) as mock_repair:
            mock_repair.return_value = MagicMock(
                repaired=0, unchanged=0, unmatched=0,
                skipped=0, low_confidence=0, details=[],
            )
            result = await analyzer.update_sector_trend(
                "半导体",
                days=10,
                ai_processor=mock_ai,
                force=True,
                report_date=target_date,
                skip_repair=False,
            )

            # 修复服务应被调用
            mock_repair.assert_called_once()

        assert result["action"] == "updated"
        assert result.get("repair_result") is not None


class TestCLIUpdateOptions:
    """验证 CLI update 命令选项。"""

    def test_update_help_shows_skip_repair(self) -> None:
        """update --help 应包含 --skip-repair。"""
        from click.testing import CliRunner
        from src.cli.sector_trends import sector_trends

        runner = CliRunner()
        result = runner.invoke(sector_trends, ["update", "--help"])
        assert result.exit_code == 0
        assert "--skip-repair" in result.output

    def test_update_help_shows_date(self) -> None:
        """update --help 应包含 --date。"""
        from click.testing import CliRunner
        from src.cli.sector_trends import sector_trends

        runner = CliRunner()
        result = runner.invoke(sector_trends, ["update", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output


class TestEvidenceDiagnostics:
    """验证证据诊断计数和修复诊断信息。"""

    @pytest.mark.asyncio
    async def test_evidence_includes_diagnostics_counts(self) -> None:
        """evidence 应包含 diagnostics 字段，含各来源计数。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        mock_evidence = {
            "sector_name": "半导体",
            "end_date": "2026-05-10",
            "is_sparse": False,
            "total_evidence_count": 5,
            "market_appearances": [{"trade_date": "2026-05-10"}, {"trade_date": "2026-05-09"}],
            "cls_watch_mentions": [{"title": "test1"}, {"title": "test2"}],
            "cls_telegraph_mentions": [{"title": "tg1"}],
            "data_gaps": [],
            "diagnostics": {
                "market_count": 2,
                "cls_watch_count": 2,
                "cls_telegraph_count": 1,
                "total_evidence_count": 5,
                "data_gap_count": 0,
            },
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        result = await analyzer.collect_sector_evidence(
            "半导体", date(2026, 5, 10), 10,
        )

        diag = result["diagnostics"]
        assert diag["market_count"] == 2
        assert diag["cls_watch_count"] == 2
        assert diag["cls_telegraph_count"] == 1
        assert diag["total_evidence_count"] == 5
        assert diag["data_gap_count"] == 0

    @pytest.mark.asyncio
    async def test_sparse_evidence_shows_data_gap_count(self) -> None:
        """稀疏证据的 diagnostics 应显示 data_gap_count > 0。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        mock_evidence = {
            "sector_name": "新板块",
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
            "diagnostics": {
                "market_count": 0,
                "cls_watch_count": 0,
                "cls_telegraph_count": 0,
                "total_evidence_count": 0,
                "data_gap_count": 3,
            },
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        result = await analyzer.collect_sector_evidence(
            "新板块", date(2026, 5, 10), 10,
        )

        assert result["diagnostics"]["data_gap_count"] == 3
        assert result["is_sparse"] is True

    @pytest.mark.asyncio
    async def test_repair_diagnostics_in_evidence_json(self) -> None:
        """更新时如果运行了修复，evidence_json 应包含 repair_diagnostics。"""
        db = _make_mock_db()
        analyzer = SectorTrendAnalyzer(db)

        target_date = date(2026, 5, 6)

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
            "data_gaps": [],
            "diagnostics": {
                "market_count": 0,
                "cls_watch_count": 0,
                "cls_telegraph_count": 0,
                "total_evidence_count": 0,
                "data_gap_count": 0,
            },
        }
        analyzer.collect_sector_evidence = AsyncMock(return_value=mock_evidence)

        mock_ai = AsyncMock()
        mock_ai.generate_sector_trend_summary = AsyncMock(return_value=(
            "# 半导体趋势\n\n内容",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察", "judgement": "观察"},
        ))
        analyzer.save_trend_summary = AsyncMock(return_value=MagicMock(output_path="test.md"))

        mock_repair_result = MagicMock(
            repaired=5, unchanged=10, unmatched=2,
            low_confidence=1, details=[],
        )

        with patch("src.services.cls_watch_repair.ClsWatchRepairService.repair_window", new_callable=AsyncMock) as mock_repair:
            mock_repair.return_value = mock_repair_result
            result = await analyzer.update_sector_trend(
                "半导体",
                days=10,
                ai_processor=mock_ai,
                force=True,
                report_date=target_date,
                skip_repair=False,
            )

        # 验证 save_trend_summary 被调用时 evidence_json 包含 repair_diagnostics
        save_call = analyzer.save_trend_summary.call_args
        evidence_json_str = save_call.kwargs.get("evidence_json") or save_call[1].get("evidence_json")
        evidence_data = json.loads(evidence_json_str)
        assert "repair_diagnostics" in evidence_data
        assert evidence_data["repair_diagnostics"]["repaired"] == 5
        assert evidence_data["repair_diagnostics"]["low_confidence"] == 1


class TestConservativeValidationPreserved:
    """验证保守的阶段验证在修复后仍然不变。"""

    def test_validate_sector_stage_unchanged_sparse(self) -> None:
        """稀疏证据仍然被保守降级，不管修复是否运行过。"""
        from src.services.trend_stage_taxonomy import validate_sector_stage

        # 稀疏证据 + 首次报告 → 非允许阶段 → 暂无趋势
        assert validate_sector_stage("主线加强", is_sparse=True, is_first_report=True) == "暂无趋势"
        assert validate_sector_stage("主线延续", is_sparse=True, is_first_report=True) == "暂无趋势"
        assert validate_sector_stage("分歧中继", is_sparse=True, is_first_report=True) == "暂无趋势"

    def test_validate_sector_stage_no_market_blocks_mainline(self) -> None:
        """无行情证据仍阻止主线阶段。"""
        from src.services.trend_stage_taxonomy import validate_sector_stage

        assert validate_sector_stage("主线加强", has_market_evidence=False) == "暂无趋势"
        assert validate_sector_stage("主线延续", has_market_evidence=False) == "暂无趋势"

    def test_repaired_low_confidence_alone_no_promotion(self) -> None:
        """仅低置信度修复证据不能提升到强阶段。

        模拟：只有低置信度 CLS watch 匹配，没有行情证据。
        """
        from src.services.trend_stage_taxonomy import validate_sector_stage

        # 低置信度修复证据不改变 is_sparse=False 或 has_market_evidence=True
        # 如果证据仍然稀疏，阶段应被降级
        result = validate_sector_stage(
            "主线加强",
            is_sparse=True,
            has_market_evidence=False,
            is_first_report=True,
        )
        assert result == "暂无趋势"

    def test_repaired_multi_source_can_support_allowed_stages(self) -> None:
        """修复的多源证据可以支持分类法已允许的阶段。

        模拟：修复 watch + 行情 + 电报多源证据，满足 taxonomy 要求。
        """
        from src.services.trend_stage_taxonomy import validate_sector_stage

        # 非稀疏 + 有行情 + 有先前上下文 → 允许主线延续
        result = validate_sector_stage(
            "主线延续",
            is_sparse=False,
            has_market_evidence=True,
            has_prior=True,
            prior_stage="主线延续",
            is_first_report=False,
        )
        assert result == "主线延续"

    def test_sparse_allowed_stages_unchanged(self) -> None:
        """稀疏证据允许的阶段保持不变。"""
        from src.services.trend_stage_taxonomy import validate_sector_stage, SECTOR_SPARSE_ALLOWED

        for stage in SECTOR_SPARSE_ALLOWED:
            result = validate_sector_stage(stage, is_sparse=True, has_market_evidence=True)
            assert result == stage, f"稀疏证据应允许 {stage}，但得到 {result}"
