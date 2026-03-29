"""python -m src.cli 模块入口回归测试。

验证 python -m src.cli 入口的可用性、命令树一致性和子命令完整性。
参考 spec: cli-entrypoint-compatibility/spec.md
"""

import subprocess

import pytest
from click.testing import CliRunner

from src.cli import main
from src.cli.main import main as main_from_module

PROJECT_ROOT = "/Users/jie.hua/Documents/Developments/Projects/wchat_doc"


class TestModuleEntrypointHelp:
    """场景 1 & 2: python -m src.cli --help 和 python -m src.cli ai --help 可执行。"""

    def test_top_level_help_exits_zero(self) -> None:
        """python -m src.cli --help 应正常退出 (exit_code == 0)。"""
        result = subprocess.run(
            ["python", "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"退出码应为 0，实际为 {result.returncode}。stderr: {result.stderr}"
        )

    def test_top_level_help_contains_wchat_keyword(self) -> None:
        """python -m src.cli --help 输出应包含 'wchat' 或 '微信'。"""
        result = subprocess.run(
            ["python", "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        output = result.stdout + result.stderr
        assert "wchat" in output.lower() or "微信" in output, (
            f"输出中应包含 'wchat' 或 '微信'，实际输出:\n{output}"
        )

    def test_ai_help_exits_zero(self) -> None:
        """python -m src.cli ai --help 应正常退出 (exit_code == 0)。"""
        result = subprocess.run(
            ["python", "-m", "src.cli", "ai", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"退出码应为 0，实际为 {result.returncode}。stderr: {result.stderr}"
        )

    def test_ai_help_contains_ai_keyword(self) -> None:
        """python -m src.cli ai --help 输出应包含 'AI' 或 'ai'。"""
        result = subprocess.run(
            ["python", "-m", "src.cli", "ai", "--help"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        output = result.stdout + result.stderr
        assert "AI" in output or "ai" in output, (
            f"输出中应包含 'AI' 或 'ai'，实际输出:\n{output}"
        )


class TestModuleEntrypointIdentity:
    """场景 3: 模块入口与安装脚本入口共用同一命令树。"""

    def test_main_is_same_object(self) -> None:
        """src.cli.main 和 src.cli 包导出的 main 应为同一个对象。"""
        assert main is main_from_module, (
            "src.cli 导出的 main 和 src.cli.main.main 应为同一个对象"
        )

    def test_main_commands_are_same_object(self) -> None:
        """main.commands 应与 main_from_module.commands 是同一个对象。"""
        assert main.commands is main_from_module.commands, (
            "两个入口的 commands 字典应为同一个对象"
        )

    def test_top_level_commands_include_all_expected(self) -> None:
        """顶层命令列表应包含所有预期命令。"""
        expected_commands = {
            "init",
            "version",
            "login",
            "logout",
            "subscribe",
            "unsubscribe",
            "fetch",
            "ls",
            "info",
            "show",
            "article",
            "export",
            "ai",
            "cls",
        }
        actual_commands = set(main.commands.keys())
        missing = expected_commands - actual_commands
        assert not missing, (
            f"缺少以下顶层命令: {missing}。实际命令: {sorted(actual_commands)}"
        )


class TestAiSubcommands:
    """场景 4: ai 子命令列表一致。"""

    def test_ai_subcommands_include_all_expected(self) -> None:
        """ai 命令组的子命令应包含所有预期子命令。"""
        expected_subcommands = {
            "summarize",
            "keywords",
            "classify",
            "sentiment",
            "batch-summarize",
            "extract-stocks",
            "market-summary",
            "stocks",
        }
        ai_group = main.commands["ai"]
        actual_subcommands = set(ai_group.commands.keys())
        missing = expected_subcommands - actual_subcommands
        assert not missing, (
            f"ai 子命令缺少: {missing}。实际子命令: {sorted(actual_subcommands)}"
        )

    def test_ai_subcommand_help_via_runner(self) -> None:
        """通过 CliRunner 验证 ai --help 输出包含所有子命令名称。"""
        runner = CliRunner()
        result = runner.invoke(main, ["ai", "--help"])
        assert result.exit_code == 0, f"ai --help 退出码应为 0，实际为 {result.exit_code}"

        expected_names = [
            "summarize",
            "keywords",
            "classify",
            "sentiment",
            "batch-summarize",
            "extract-stocks",
            "market-summary",
            "stocks",
        ]
        for name in expected_names:
            assert name in result.output, (
                f"ai --help 输出中应包含子命令 '{name}'。实际输出:\n{result.output}"
            )
