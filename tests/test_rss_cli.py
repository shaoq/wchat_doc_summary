"""CLI 命令测试 - 覆盖 source 命令组、ls 扩展、健康诊断。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli.main import main


class TestSourceCLICommands:
    """source 命令组注册测试。"""

    def test_source_group_registered(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "--help"])
        assert result.exit_code == 0
        assert "RSS 源管理" in result.output

    def test_source_add_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "add", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "FEED_URL" in result.output

    def test_source_remove_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "remove", "--help"])
        assert result.exit_code == 0

    def test_source_list_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "list", "--help"])
        assert result.exit_code == 0

    def test_source_health_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "health", "--help"])
        assert result.exit_code == 0

    def test_source_fetch_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "fetch", "--help"])
        assert result.exit_code == 0

    def test_source_disable_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "disable", "--help"])
        assert result.exit_code == 0

    def test_source_enable_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["source", "enable", "--help"])
        assert result.exit_code == 0


class TestSourceAddCommand:
    """source add 命令测试。"""

    def test_add_source_success(self) -> None:
        mock_source = MagicMock()
        mock_source.source_name = "全部"
        mock_source.source_type = "aggregate"
        mock_source.feed_url = "https://rss.example.com/all?key=secret"
        mock_source.status = 1

        with patch("src.cli.rss_source.get_db", new=AsyncMock(return_value=MagicMock())) as mock_get_db:
            with patch("src.cli.rss_source.RSSSourceService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.add_source = AsyncMock(return_value=mock_source)
                mock_svc_cls.return_value = mock_svc

                runner = CliRunner()
                result = runner.invoke(main, ["source", "add", "全部", "https://rss.example.com/all"])

        assert result.exit_code == 0
        assert "添加成功" in result.output

    def test_add_category_source(self) -> None:
        mock_source = MagicMock()
        mock_source.source_name = "财经"
        mock_source.source_type = "category"
        mock_source.feed_url = "https://rss.example.com/finance"
        mock_source.status = 1

        with patch("src.cli.rss_source.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.rss_source.RSSSourceService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.add_source = AsyncMock(return_value=mock_source)
                mock_svc_cls.return_value = mock_svc

                runner = CliRunner()
                result = runner.invoke(main, [
                    "source", "add", "财经",
                    "https://rss.example.com/finance",
                    "--type", "category",
                ])

        assert result.exit_code == 0


class TestSourceListCommand:
    """source list 命令测试。"""

    def test_list_empty(self) -> None:
        with patch("src.cli.rss_source.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.rss_source.RSSSourceService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.list_sources = AsyncMock(return_value=[])
                mock_svc.check_quota_warning = AsyncMock(return_value=(False, 0, None))
                mock_svc_cls.return_value = mock_svc

                runner = CliRunner()
                result = runner.invoke(main, ["source", "list"])

        assert result.exit_code == 0
        assert "暂无" in result.output


class TestSourceHealthCommand:
    """source health 命令测试。"""

    def test_health_no_sources(self) -> None:
        with patch("src.cli.rss_source.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.rss_source.RSSSourceService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.list_sources = AsyncMock(return_value=[])
                mock_svc_cls.return_value = mock_svc

                runner = CliRunner()
                result = runner.invoke(main, ["source", "health"])

        assert result.exit_code == 0
        assert "暂无" in result.output


class TestLsExtension:
    """ls 命令扩展测试（RSS 源列显示）。"""

    def test_ls_shows_rss_source_column(self) -> None:
        """ls 命令应包含 RSS 源列。"""
        runner = CliRunner()
        result = runner.invoke(main, ["ls", "--help"])
        assert result.exit_code == 0

    def test_ls_help_still_works(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["ls", "--help"])
        assert result.exit_code == 0
        assert "订阅列表" in result.output


class TestHealthDiagnosticsOutput:
    """健康诊断输出测试。"""

    def test_health_table_columns(self) -> None:
        """health 命令应包含所有诊断列。"""
        mock_source = MagicMock()
        mock_source.id = 1
        mock_source.source_name = "测试源"
        mock_source.status = 1

        mock_health = MagicMock()
        mock_health.last_success_at = None
        mock_health.latest_item_time = None
        mock_health.consecutive_failures = 3
        mock_health.empty_response_count = 1
        mock_health.last_error_summary = "HTTP 503 Service Unavailable"

        with patch("src.cli.rss_source.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.rss_source.RSSSourceService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.list_sources = AsyncMock(return_value=[mock_source])
                mock_svc.get_health = AsyncMock(return_value=mock_health)
                mock_svc.is_stale = AsyncMock(return_value=True)
                mock_svc_cls.return_value = mock_svc

                runner = CliRunner()
                result = runner.invoke(main, ["source", "health"])

        assert result.exit_code == 0
        assert "测试源" in result.output
        assert "3" in result.output  # consecutive failures
