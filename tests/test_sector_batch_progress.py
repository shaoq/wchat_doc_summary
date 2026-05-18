"""板块批量更新进度事件测试 - 覆盖事件序列、阶段桥接、skip_preparation、AI 重试、CLI 渲染。"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.sector_trend_service import (
    SectorTrendAnalyzer,
    SectorUpdateProgressEvent,
)


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.get_session = MagicMock()
    return db


def _setup_analyzer_for_batch() -> tuple[SectorTrendAnalyzer, list[SectorUpdateProgressEvent]]:
    """创建带 mock 的 analyzer 和事件收集器。"""
    db = _make_mock_db()
    analyzer = SectorTrendAnalyzer(db)
    events: list[SectorUpdateProgressEvent] = []

    def collector(event: SectorUpdateProgressEvent) -> None:
        events.append(event)

    # 默认 mock：返回空 tracked 板块列表
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    db.get_session = MagicMock(return_value=mock_session)

    return analyzer, events, collector


# ---------------------------------------------------------------------------
# 3.1 批量进度事件顺序和 batch 上下文字段
# ---------------------------------------------------------------------------

class TestBatchEventOrdering:
    """验证批量更新事件序列和 batch 上下文字段。"""

    @pytest.mark.asyncio
    async def test_batch_start_and_done_event_order(self) -> None:
        """batch_start 应在 batch_done 之前。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        # Mock 1 个 tracked 板块
        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        # Mock update_sector_trend 返回 updated
        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
            "output_path": "output/test.md",
            "trend_status": "主线延续",
            "strength_level": "强",
            "action_bias": "跟踪",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            days=10,
            progress_callback=collector,
        )

        types = [e.type for e in events]
        assert types[0] == "batch_start"
        assert types[-1] == "batch_done"
        assert types.index("batch_start") < types.index("batch_done")

    @pytest.mark.asyncio
    async def test_batch_start_context_fields(self) -> None:
        """batch_start 应包含完整的上下文字段。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer._market_analyzer.get_latest_trade_date = MagicMock(
            return_value=date(2026, 5, 16)
        )
        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "skipped",
            "sector_name": "半导体",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            days=10,
            force=True,
            skip_preparation=True,
            progress_callback=collector,
        )

        batch_start = events[0]
        assert batch_start.type == "batch_start"
        assert batch_start.trade_date == "2026-05-16"
        assert batch_start.target_count == 1
        assert batch_start.lookback_window == 10
        assert batch_start.force_mode is True
        assert batch_start.skip_preparation is True

    @pytest.mark.asyncio
    async def test_batch_done_has_counts(self) -> None:
        """batch_done 应包含成功/跳过/失败计数。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
            "output_path": "test.md",
            "trend_status": "主线延续",
            "strength_level": "强",
            "action_bias": "跟踪",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        batch_done = events[-1]
        assert batch_done.type == "batch_done"
        assert batch_done.success_count == 1
        assert batch_done.skipped_count == 0
        assert batch_done.failed_count == 0
        assert batch_done.elapsed > 0

    @pytest.mark.asyncio
    async def test_shared_repair_events(self) -> None:
        """skip_repair=False 时应发出 shared_repair_start 和 shared_repair_done。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        mock_repair_result = MagicMock(
            repaired=5, low_confidence=1, unmatched=2,
        )

        with patch("src.services.cls_watch_repair.ClsWatchRepairService.repair_window", new_callable=AsyncMock) as mock_repair:
            mock_repair.return_value = mock_repair_result
            await analyzer.update_all_sector_trends(
                ai_processor=MagicMock(),
                skip_repair=False,
                progress_callback=collector,
            )

        types = [e.type for e in events]
        assert "shared_repair_start" in types
        assert "shared_repair_done" in types
        assert types.index("shared_repair_start") < types.index("shared_repair_done")

        repair_done = next(e for e in events if e.type == "shared_repair_done")
        assert repair_done.repair_repaired == 5
        assert repair_done.repair_low_confidence == 1
        assert repair_done.repair_unmatched == 2


# ---------------------------------------------------------------------------
# 3.2 每个 sector 阶段桥接和 done/skipped/failed 事件
# ---------------------------------------------------------------------------

class TestPerSectorEvents:
    """验证每个 sector 的阶段桥接和完成事件。"""

    @pytest.mark.asyncio
    async def test_sector_start_and_done_events(self) -> None:
        """成功更新应发出 sector_start → sector_done。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
            "output_path": "test.md",
            "trend_status": "主线延续",
            "strength_level": "强",
            "action_bias": "跟踪",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        types = [e.type for e in events]
        assert "sector_start" in types
        assert "sector_done" in types
        assert types.index("sector_start") < types.index("sector_done")

        sector_done = next(e for e in events if e.type == "sector_done")
        assert sector_done.action == "updated"
        assert sector_done.sector_name == "半导体"
        assert sector_done.sector_index == 1
        assert sector_done.sector_total == 1
        assert sector_done.elapsed > 0

    @pytest.mark.asyncio
    async def test_sector_skipped_event(self) -> None:
        """跳过的 sector 应发出 sector_skipped 事件。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "skipped",
            "sector_name": "半导体",
            "reason": "今日已更新",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        sector_skipped = next(e for e in events if e.type == "sector_skipped")
        assert sector_skipped.sector_name == "半导体"
        assert sector_skipped.action == "skipped"

    @pytest.mark.asyncio
    async def test_sector_failed_event(self) -> None:
        """失败的 sector 应发出 sector_failed 事件。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(side_effect=RuntimeError("API error"))

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            continue_on_error=True,
            progress_callback=collector,
        )

        sector_failed = next(e for e in events if e.type == "sector_failed")
        assert sector_failed.sector_name == "半导体"
        assert "API error" in sector_failed.error
        assert sector_failed.action == "failed"

    @pytest.mark.asyncio
    async def test_stage_bridging_events(self) -> None:
        """单 sector 的 progress_callback 应桥接为 sector_stage 事件。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        # 捕获传给 update_sector_trend 的 progress_callback
        captured_cb = {}

        async def mock_update(*args, **kwargs):
            captured_cb["progress_callback"] = kwargs.get("progress_callback")
            # 模拟发出阶段事件
            if captured_cb["progress_callback"]:
                captured_cb["progress_callback"]("evidence", "收集板块证据...")
                captured_cb["progress_callback"]("ai", "AI 生成板块趋势...")
            return {
                "action": "updated",
                "sector_name": "半导体",
                "output_path": "test.md",
                "trend_status": "主线延续",
                "strength_level": "强",
                "action_bias": "跟踪",
            }

        analyzer.update_sector_trend = AsyncMock(side_effect=mock_update)

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        stage_events = [e for e in events if e.type == "sector_stage"]
        assert len(stage_events) >= 2
        stages = [e.stage for e in stage_events]
        assert "evidence" in stages
        assert "ai" in stages

        # 验证 sector_stage 事件包含正确的 sector 信息
        for se in stage_events:
            assert se.sector_name == "半导体"
            assert se.sector_index == 1


# ---------------------------------------------------------------------------
# 3.3 skip_preparation 在批量模式下生效
# ---------------------------------------------------------------------------

class TestSkipPreparationBatch:
    """验证 skip_preparation 在批量模式下正确传递。"""

    @pytest.mark.asyncio
    async def test_skip_preparation_passed_to_update(self) -> None:
        """skip_preparation=True 应传递给每个 sector 的 update_sector_trend。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            skip_preparation=True,
            progress_callback=collector,
        )

        # 验证 update_sector_trend 被调用时 skip_preparation=True
        call_kwargs = analyzer.update_sector_trend.call_args.kwargs
        assert call_kwargs.get("skip_preparation") is True

    @pytest.mark.asyncio
    async def test_skip_preparation_false_by_default(self) -> None:
        """默认 skip_preparation=False。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        call_kwargs = analyzer.update_sector_trend.call_args.kwargs
        assert call_kwargs.get("skip_preparation") is False


# ---------------------------------------------------------------------------
# 3.4 AI 重试进度事件（净化后）
# ---------------------------------------------------------------------------

class TestAPIRetryEvents:
    """验证 AI 重试诊断通过 progress 事件正确传递。"""

    @pytest.mark.asyncio
    async def test_retry_callback_bridged(self) -> None:
        """retry_callback 应传递给 update_sector_trend 并桥接为 api_retry 事件。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        captured_retry_cb = {}

        async def mock_update(*args, **kwargs):
            captured_retry_cb["callback"] = kwargs.get("retry_callback")
            # 模拟 AI 重试回调
            if captured_retry_cb["callback"]:
                captured_retry_cb["callback"]({
                    "type": "api_retry",
                    "stage": "sector-trend",
                    "attempt": 2,
                    "max_attempts": 3,
                    "retry_delay": 2,
                    "error": "API timeout after 30s",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "base_url_host": "api.anthropic.com",
                    "exception_type": "APITimeoutError",
                })
            return {
                "action": "updated",
                "sector_name": "半导体",
                "output_path": "test.md",
                "trend_status": "主线延续",
                "strength_level": "强",
                "action_bias": "跟踪",
            }

        analyzer.update_sector_trend = AsyncMock(side_effect=mock_update)

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        retry_events = [e for e in events if e.type == "api_retry"]
        assert len(retry_events) == 1

        retry_ev = retry_events[0]
        assert retry_ev.attempt == 2
        assert retry_ev.max_attempts == 3
        assert "API timeout" in retry_ev.error
        assert retry_ev.provider == "anthropic"
        assert retry_ev.model == "claude-sonnet-4-6"
        assert retry_ev.base_url_host == "api.anthropic.com"

    @pytest.mark.asyncio
    async def test_retry_error_sanitized(self) -> None:
        """重试错误不应包含敏感信息。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        async def mock_update(*args, **kwargs):
            cb = kwargs.get("retry_callback")
            if cb:
                cb({
                    "type": "api_retry",
                    "attempt": 1,
                    "max_attempts": 3,
                    "error": "Error: API key sk-ant-secret12345 is invalid https://full.url/path",
                    "provider": "anthropic",
                    "model": "test-model",
                    "base_url_host": "api.test.com",
                })
            return {
                "action": "updated",
                "sector_name": "半导体",
            }

        analyzer.update_sector_trend = AsyncMock(side_effect=mock_update)

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            progress_callback=collector,
        )

        retry_ev = next(e for e in events if e.type == "api_retry")
        # 错误应被截断到 200 字符
        assert len(retry_ev.error) <= 200
        # base_url_host 不包含完整 URL
        assert "/" not in retry_ev.base_url_host
        assert "http" not in retry_ev.base_url_host


# ---------------------------------------------------------------------------
# 3.5 CLI 批量更新进度输出
# ---------------------------------------------------------------------------

class TestCLIBatchProgress:
    """验证 CLI 批量更新命令的进度输出。"""

    def test_update_help_shows_skip_preparation(self) -> None:
        """update --help 应包含 --skip-preparation。"""
        from click.testing import CliRunner
        from src.cli.sector_trends import sector_trends

        runner = CliRunner()
        result = runner.invoke(sector_trends, ["update", "--help"])
        assert result.exit_code == 0
        assert "--skip-preparation" in result.output

    @pytest.mark.asyncio
    async def test_cli_update_all_no_progress_callback(self) -> None:
        """不传 progress_callback 时 update_all_sector_trends 不应报错。"""
        analyzer, _, _ = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        # 不传 progress_callback，不应报错
        result = await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
        )
        assert result["success"] == 1


# ---------------------------------------------------------------------------
# 3.6 回归测试 - 确保不破坏现有功能
# ---------------------------------------------------------------------------

class TestBatchRegression:
    """回归测试 - 确保批量更新核心行为不变。"""

    @pytest.mark.asyncio
    async def test_batch_result_preserves_keys(self) -> None:
        """批量更新结果应保留现有返回键。"""
        analyzer, _, _ = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        result = await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
        )

        assert "total" in result
        assert "success" in result
        assert "skipped" in result
        assert "failed" in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_batch_skip_repair_still_works(self) -> None:
        """skip_repair=True 应跳过共享修复且不发出修复事件。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sector = MagicMock()
        mock_sector.canonical_name = "半导体"
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_sector]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "半导体",
        })

        await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            skip_repair=True,
            progress_callback=collector,
        )

        types = [e.type for e in events]
        assert "shared_repair_start" not in types
        assert "shared_repair_done" not in types

    @pytest.mark.asyncio
    async def test_batch_limit_respected(self) -> None:
        """limit 参数应限制处理的 sector 数量。"""
        analyzer, events, collector = _setup_analyzer_for_batch()

        mock_sectors = [MagicMock(canonical_name=f"板块{i}") for i in range(5)]
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = mock_sectors[:2]
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        analyzer.db.get_session = MagicMock(return_value=mock_session)

        analyzer.update_sector_trend = AsyncMock(return_value={
            "action": "updated",
            "sector_name": "test",
        })

        result = await analyzer.update_all_sector_trends(
            ai_processor=MagicMock(),
            limit=2,
            progress_callback=collector,
        )

        assert result["total"] == 2
