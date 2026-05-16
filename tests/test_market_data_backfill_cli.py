"""市场数据回填 CLI 测试 - help 输出、日期校验、渲染、无 summary 创建。"""

import pytest
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch, MagicMock

from src.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestMarketDataHelp:
    """验证 help 输出包含 backfill 子命令和 --date 选项。"""

    def test_market_data_help_shows_backfill(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["ai", "market-data", "--help"])
        assert result.exit_code == 0
        assert "backfill" in result.output

    def test_backfill_help_shows_date_option(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["ai", "market-data", "backfill", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output


class TestInvalidDateHandling:
    """验证无效日期被拒绝。"""

    def test_invalid_date_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["ai", "market-data", "backfill", "--date", "invalid"])
        assert "日期格式错误" in result.output

    def test_malformed_date_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["ai", "market-data", "backfill", "--date", "2026/05/15"])
        assert "日期格式错误" in result.output


class TestSuccessfulPartialBackfillRendering:
    """验证部分成功的回填渲染。"""

    def test_renders_populated_and_skipped(self, runner: CliRunner) -> None:
        from src.services.market_data_backfill_service import BackfillResult, CategoryOutcome
        from datetime import date

        mock_result = BackfillResult(
            trade_date=date(2026, 5, 15),
            outcomes=(
                CategoryOutcome(category="volume", status="populated", record_count=1, message="volume 已写入 1 条记录"),
                CategoryOutcome(category="limit_up", status="empty", message="limit_up 无数据"),
                CategoryOutcome(category="indices", status="skipped_unsupported", message="仅实时快照"),
                CategoryOutcome(category="statistics", status="skipped_unsupported", message="pytdx 实时报价"),
                CategoryOutcome(category="sectors", status="skipped_unsupported", message="仅实时快照"),
                CategoryOutcome(category="snapshot", status="skipped_unsupported", message="仅实时"),
            ),
            total_populated=1,
            total_skipped=4,
            total_empty=1,
            total_failed=0,
        )

        with patch("src.cli.market_data.get_db") as mock_get_db, \
             patch("src.services.market_data_backfill_service.MarketDataBackfillService") as mock_service_cls:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            mock_service = MagicMock()
            mock_service.backfill = AsyncMock(return_value=mock_result)
            mock_service_cls.return_value = mock_service

            result = runner.invoke(main, ["ai", "market-data", "backfill", "--date", "2026-05-15"])

            assert result.exit_code == 0
            assert "volume" in result.output
            assert "populated" in result.output or "已写入" in result.output
            assert "部分完成" in result.output


class TestNoMarketSummaryCreated:
    """验证 backfill 不调用 AI 或创建 market summary。"""

    def test_no_ai_processor_imported(self, runner: CliRunner) -> None:
        """backfill 命令不应导入或使用 AIProcessor。"""
        import src.cli.market_data as market_data_module
        source = open(market_data_module.__file__, "r").read()
        assert "AIProcessor" not in source
        assert "generate_market_summary" not in source
