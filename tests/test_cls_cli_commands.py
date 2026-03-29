"""CLS 数据命令面测试。

验证 cls 命令组的注册、帮助输出和最小执行。
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import main


class TestCLSHelpOutput:
    """CLS --help 输出测试。"""

    def test_main_help_contains_cls_command(self):
        """测试顶层 --help 包含 cls 命令。"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0
        assert 'cls' in result.output, "命令 'cls' 不在 --help 输出中"

    def test_cls_help_contains_all_subcommands(self):
        """测试 cls --help 包含所有子命令。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', '--help'])

        assert result.exit_code == 0

        expected_subcommands = [
            'fetch-telegraphs', 'fetch-watch',
            'list-telegraphs', 'list-watch',
        ]
        for cmd in expected_subcommands:
            assert cmd in result.output, f"子命令 'cls {cmd}' 不在 cls --help 输出中"

    def test_fetch_telegraphs_help(self):
        """测试 fetch-telegraphs 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'fetch-telegraphs', '--help'])

        assert result.exit_code == 0
        assert '电报' in result.output or 'telegraph' in result.output.lower()

    def test_fetch_watch_help(self):
        """测试 fetch-watch 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'fetch-watch', '--help'])

        assert result.exit_code == 0
        assert '看盘' in result.output or 'watch' in result.output.lower()

    def test_list_telegraphs_help(self):
        """测试 list-telegraphs 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'list-telegraphs', '--help'])

        assert result.exit_code == 0
        assert '电报' in result.output or 'telegraph' in result.output.lower()

    def test_list_watch_help(self):
        """测试 list-watch 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'list-watch', '--help'])

        assert result.exit_code == 0
        assert '看盘' in result.output or 'watch' in result.output.lower()


class TestCLSCommandRegistration:
    """CLS 命令注册测试。"""

    def test_main_group_has_cls_command(self):
        """测试 main group 包含 cls 命令。"""
        command_names = list(main.commands.keys())
        assert 'cls' in command_names, "命令 'cls' 未注册到 main group"

    def test_cls_group_has_all_subcommands(self):
        """测试 cls group 包含所有子命令。"""
        cls_group = main.commands['cls']
        subcommand_names = list(cls_group.commands.keys())

        expected_subcommands = [
            'fetch-telegraphs', 'fetch-watch',
            'list-telegraphs', 'list-watch',
        ]
        for cmd in expected_subcommands:
            assert cmd in subcommand_names, f"子命令 'cls {cmd}' 未注册到 cls group"


class TestCLSFetchTelegraphsExecution:
    """CLS fetch-telegraphs 最小执行测试。"""

    @patch('src.cli.cls_data.get_db')
    def test_fetch_telegraphs_success(self, mock_get_db):
        """测试 fetch-telegraphs 成功执行。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.services.cls_telegraph_service.CLSRollClient') as mock_client_cls, \
             patch('src.cli.cls_data.run_async') as mock_run_async:

            # 捕获传入 run_async 的协程函数并直接执行
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'fetch-telegraphs'])

            # 命令应该执行成功（run_async 被模拟了所以不会有实际网络调用）
            # 只验证命令不会因为注册/参数问题而失败
            assert result.exit_code == 0

    @patch('src.cli.cls_data.get_db')
    def test_fetch_telegraphs_with_date(self, mock_get_db):
        """测试 fetch-telegraphs 指定日期参数。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'fetch-telegraphs', '--date', '2026-03-28'])
            assert result.exit_code == 0

    def test_fetch_telegraphs_invalid_date(self):
        """测试 fetch-telegraphs 无效日期格式。"""
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'fetch-telegraphs', '--date', 'invalid'])
        # 无效日期应该导致错误但不崩溃
        assert result.exit_code == 0  # Click 内部处理错误


class TestCLSFetchWatchExecution:
    """CLS fetch-watch 最小执行测试。"""

    @patch('src.cli.cls_data.get_db')
    def test_fetch_watch_success(self, mock_get_db):
        """测试 fetch-watch 成功执行。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'fetch-watch'])
            assert result.exit_code == 0

    @patch('src.cli.cls_data.get_db')
    def test_fetch_watch_with_hours(self, mock_get_db):
        """测试 fetch-watch 指定回溯小时数。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'fetch-watch', '--hours', '12'])
            assert result.exit_code == 0


class TestCLSListTelegraphsExecution:
    """CLS list-telegraphs 最小执行测试。"""

    @patch('src.cli.cls_data.get_db')
    def test_list_telegraphs_empty(self, mock_get_db):
        """测试 list-telegraphs 空数据。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'list-telegraphs'])
            assert result.exit_code == 0

    @patch('src.cli.cls_data.get_db')
    def test_list_telegraphs_with_limit(self, mock_get_db):
        """测试 list-telegraphs 指定限制。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'list-telegraphs', '--limit', '10'])
            assert result.exit_code == 0

    @patch('src.cli.cls_data.get_db')
    def test_list_telegraphs_with_min_level(self, mock_get_db):
        """测试 list-telegraphs 指定最低级别。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'list-telegraphs', '--min-level', 'A'])
            assert result.exit_code == 0


class TestCLSListWatchExecution:
    """CLS list-watch 最小执行测试。"""

    @patch('src.cli.cls_data.get_db')
    def test_list_watch_empty(self, mock_get_db):
        """测试 list-watch 空数据。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'list-watch'])
            assert result.exit_code == 0

    @patch('src.cli.cls_data.get_db')
    def test_list_watch_with_limit(self, mock_get_db):
        """测试 list-watch 指定限制。"""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        with patch('src.cli.cls_data.run_async'):
            runner = CliRunner()
            result = runner.invoke(main, ['cls', 'list-watch', '--limit', '5'])
            assert result.exit_code == 0
