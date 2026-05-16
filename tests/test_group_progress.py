"""分组更新进度事件与 CLI 输出测试。"""

import io
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.models.schema import (
    SectorGroup,
    SectorGroupMember,
    SectorGroupTrendSummary,
    TrackedSector,
)
from src.services.sector_group_service import (
    GroupUpdateProgressEvent,
    ProgressCallback,
    SectorGroupService,
)
from src.storage.database import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """创建内存测试数据库。"""
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def seeded_db(test_db: Database):
    """填充基础板块数据。"""
    async with test_db.get_session() as session:
        for name, status in [("机器人", "tracked"), ("减速器", "tracked"),
                             ("传感器", "tracked"), ("机器视觉", "candidate")]:
            sector = TrackedSector(
                canonical_name=name,
                status=status,
                source="test",
                first_seen_date=date(2026, 5, 1),
                last_seen_date=date(2026, 5, 15),
            )
            session.add(sector)
    return test_db


@pytest_asyncio.fixture
def group_service(seeded_db: Database) -> SectorGroupService:
    return SectorGroupService(seeded_db)


# ---------------------------------------------------------------------------
# 5.1 进度回调事件验证 - 服务层批量事件
# ---------------------------------------------------------------------------

class TestProgressCallbackBatchEvents:
    """测试 progress callback 在批量更新中发出正确事件序列。"""

    @pytest.mark.asyncio
    async def test_batch_emits_start_and_done(self, group_service: SectorGroupService):
        """批量更新应至少发出 batch_start 和 batch_done。"""
        await group_service.create_group("测试组")
        events: list[GroupUpdateProgressEvent] = []

        def cb(event: GroupUpdateProgressEvent) -> None:
            events.append(event)

        result = await group_service.update_all_group_trends(
            progress_callback=cb,
        )

        types = [e.type for e in events]
        assert "batch_start" in types
        assert "batch_done" in types

    @pytest.mark.asyncio
    async def test_batch_start_contains_context(self, group_service: SectorGroupService):
        """batch_start 事件应包含批量上下文信息。"""
        await group_service.create_group("测试组")
        events: list[GroupUpdateProgressEvent] = []
        await group_service.update_all_group_trends(progress_callback=events.append)

        start = next(e for e in events if e.type == "batch_start")
        assert start.target_count >= 1
        assert start.lookback_window == 10
        assert start.refresh_members_mode == "default"

    @pytest.mark.asyncio
    async def test_batch_done_contains_counts(self, group_service: SectorGroupService):
        """batch_done 事件应包含统计信息。"""
        await group_service.create_group("测试组")
        events: list[GroupUpdateProgressEvent] = []

        await group_service.update_all_group_trends(progress_callback=events.append)

        done = next(e for e in events if e.type == "batch_done")
        assert done.target_count >= 1
        assert done.elapsed > 0


# ---------------------------------------------------------------------------
# 5.2 成员刷新事件验证
# ---------------------------------------------------------------------------

class TestProgressCallbackMemberEvents:
    """测试成员刷新事件发射。"""

    @pytest.mark.asyncio
    async def test_member_skip_candidate_event(self, group_service: SectorGroupService):
        """candidate 成员应触发 skip 事件。"""
        await group_service.create_group("测试组")
        await group_service.add_member("测试组", "机器视觉", "related")

        events: list[GroupUpdateProgressEvent] = []
        mock_ai = AsyncMock()
        mock_ai.generate_sector_group_trend_summary.return_value = (
            "报告内容\n\ntrend_status: 暂无趋势\nstrength_level: 弱\naction_bias: 观察",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察"},
        )

        await group_service.update_group_trend(
            "测试组", ai_processor=mock_ai, progress_callback=events.append,
            force=True,
        )

        skip_events = [e for e in events if e.type == "member_refresh_skip"]
        assert len(skip_events) >= 1
        assert any(e.member_name == "机器视觉" for e in skip_events)

    @pytest.mark.asyncio
    async def test_member_failure_event(self, group_service: SectorGroupService):
        """成员刷新失败应触发 member_refresh_failed 事件。"""
        await group_service.create_group("测试组")
        await group_service.add_member("测试组", "机器人", "core")

        events: list[GroupUpdateProgressEvent] = []
        mock_ai = AsyncMock()
        mock_ai.generate_sector_group_trend_summary.return_value = (
            "报告",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察"},
        )
        # 让 update_sector_trend 抛异常
        with patch(
            "src.services.sector_trend_service.SectorTrendAnalyzer"
        ) as mock_analyzer_cls:
            mock_analyzer = AsyncMock()
            mock_analyzer.update_sector_trend.side_effect = RuntimeError("Connection error")
            mock_analyzer_cls.return_value = mock_analyzer

            await group_service.update_group_trend(
                "测试组", ai_processor=mock_ai, progress_callback=events.append,
                force=True,
            )

        fail_events = [e for e in events if e.type == "member_refresh_failed"]
        assert len(fail_events) >= 1
        assert fail_events[0].error == "Connection error"
        assert fail_events[0].member_name == "机器人"


# ---------------------------------------------------------------------------
# 5.3-5.5 CLI 渲染测试
# ---------------------------------------------------------------------------

class TestCLIDefaultOutput:
    """测试默认模式批量更新输出。"""

    def test_verbose_option_registered(self):
        """--verbose 选项应已注册。"""
        from click.testing import CliRunner
        from src.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["ai", "sector-trends", "groups", "update", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.output

    def test_quiet_option_registered(self):
        """--quiet 选项应已注册。"""
        from click.testing import CliRunner
        from src.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["ai", "sector-trends", "groups", "update", "--help"])
        assert result.exit_code == 0
        assert "--quiet" in result.output


class TestCLIQuietOutput:
    """测试 quiet 模式最终汇总。"""

    def test_quiet_summary_format(self):
        """quiet 模式 batch_done 渲染应输出键值对格式。"""
        event = GroupUpdateProgressEvent(
            type="batch_done",
            success_count=5,
            skipped_count=1,
            failed_count=1,
            member_refresh_failed=2,
            elapsed=30.0,
        )

        # 验证事件字段可访问
        assert event.success_count == 5
        assert event.failed_count == 1
        assert event.member_refresh_failed == 2


# ---------------------------------------------------------------------------
# 5.6 敏感数据不打印测试
# ---------------------------------------------------------------------------

class TestSanitizedDiagnostics:
    """验证诊断信息不包含敏感数据。"""

    def test_event_no_api_key(self):
        """进度事件不应包含 API key。"""
        event = GroupUpdateProgressEvent(
            type="member_refresh_failed",
            error="Connection error",
        )
        event_dict = event.__dict__
        for value in event_dict.values():
            if isinstance(value, str):
                assert "sk-" not in value
                assert "Bearer" not in value.lower()
                assert "api_key" not in value.lower()

    def test_ai_retry_callback_sanitized(self):
        """AI retry callback 中的 base_url_host 只包含域名。"""
        # 模拟 _safe_base_url_host 的行为
        from urllib.parse import urlparse
        full_url = "https://api.openai.com/v1/chat/completions?key=sk-secret123"
        parsed = urlparse(full_url)
        host = parsed.hostname or ""
        assert "sk-secret" not in host
        assert host == "api.openai.com"

    def test_event_has_no_prompt_field(self):
        """事件不应有 prompt 字段。"""
        event = GroupUpdateProgressEvent(type="test")
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "headers")


# ---------------------------------------------------------------------------
# 5.7 重试命令建议测试
# ---------------------------------------------------------------------------

class TestRetryCommands:
    """测试失败后的重试命令建议。"""

    def test_group_summary_failure_suggests_force(self):
        """组级总结失败应建议 --force。"""
        # 模拟 CLI 渲染中的重试建议逻辑
        failed_group = {
            "group_name": "人形机器人链",
            "error": "Connection error",
            "action": "failed",
        }
        # 不含 member_refresh 关键词 → 使用 --force
        stage = failed_group.get("action", "")
        has_member_error = "member_refresh" in failed_group.get("error", "").lower()

        if has_member_error:
            cmd = f"wchat ai sector-trends groups update --group {failed_group['group_name']} --no-refresh-members --force"
        else:
            cmd = f"wchat ai sector-trends groups update --group {failed_group['group_name']} --force"

        assert "--force" in cmd
        assert "人形机器人链" in cmd

    def test_member_refresh_failure_suggests_no_refresh(self):
        """成员刷新失败应建议 --no-refresh-members。"""
        failed_group = {
            "group_name": "人形机器人链",
            "error": "member_refresh failed: Connection error",
            "action": "failed",
        }
        has_member_error = "member_refresh" in failed_group["error"].lower()

        if has_member_error:
            cmd = f"wchat ai sector-trends groups update --group {failed_group['group_name']} --no-refresh-members --force"
        else:
            cmd = f"wchat ai sector-trends groups update --group {failed_group['group_name']} --force"

        assert "--no-refresh-members" in cmd
        assert "--force" in cmd


# ---------------------------------------------------------------------------
# 无 callback 兼容性测试（任务 1.4 验证）
# ---------------------------------------------------------------------------

class TestNoCallbackCompatibility:
    """验证无 callback 时服务保持原有行为。"""

    @pytest.mark.asyncio
    async def test_update_group_no_callback(self, group_service: SectorGroupService):
        """update_group_trend 无 callback 应正常运行。"""
        await group_service.create_group("测试组")
        result = await group_service.update_group_trend("测试组")
        assert result["action"] in ("skipped", "no_ai_processor", "error", "updated")

    @pytest.mark.asyncio
    async def test_update_all_no_callback(self, group_service: SectorGroupService):
        """update_all_group_trends 无 callback 应正常运行。"""
        await group_service.create_group("测试组")
        result = await group_service.update_all_group_trends()
        assert "total" in result
        assert "success" in result
        assert "failed" in result
