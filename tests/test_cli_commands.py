"""CLI 命令面回归测试。

验证模块化后命令面保持不变。
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

from click.testing import CliRunner

from src.cli import main


class TestCLIHelpOutput:
    """CLI --help 输出回归测试。"""

    def test_main_help_contains_all_commands(self):
        """测试顶层 --help 包含所有命令。"""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0

        # 验证所有顶层命令存在
        expected_commands = [
            'init', 'version', 'login', 'logout',
            'subscribe', 'unsubscribe', 'fetch', 'ls',
            'info', 'show', 'article', 'export', 'ai', 'cls'
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"命令 '{cmd}' 不在 --help 输出中"

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

    def test_ai_help_contains_all_subcommands(self):
        """测试 ai --help 包含所有子命令。"""
        runner = CliRunner()
        result = runner.invoke(main, ['ai', '--help'])

        assert result.exit_code == 0

        # 验证所有 ai 子命令存在
        expected_subcommands = [
            'summarize', 'keywords', 'classify', 'sentiment',
            'batch-summarize', 'extract-stocks', 'market-summary', 'stocks'
        ]
        for cmd in expected_subcommands:
            assert cmd in result.output, f"子命令 'ai {cmd}' 不在 ai --help 输出中"

    def test_ai_stocks_help_contains_all_subcommands(self):
        """测试 ai stocks --help 包含所有子命令。"""
        runner = CliRunner()
        result = runner.invoke(main, ['ai', 'stocks', '--help'])

        assert result.exit_code == 0

        # 验证所有 ai stocks 子命令存在
        expected_subcommands = ['list', 'search', 'show']
        for cmd in expected_subcommands:
            assert cmd in result.output, f"子命令 'ai stocks {cmd}' 不在 ai stocks --help 输出中"


class TestCLICommandRegistration:
    """CLI 命令注册测试。"""

    def test_main_group_has_all_commands(self):
        """测试 main group 包含所有命令。"""
        command_names = list(main.commands.keys())

        expected_commands = [
            'init', 'version', 'login', 'logout',
            'subscribe', 'unsubscribe', 'fetch', 'ls',
            'info', 'show', 'article', 'export', 'ai', 'cls'
        ]
        for cmd in expected_commands:
            assert cmd in command_names, f"命令 '{cmd}' 未注册到 main group"

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

    def test_ai_group_has_all_subcommands(self):
        """测试 ai group 包含所有子命令。"""
        ai_group = main.commands['ai']
        subcommand_names = list(ai_group.commands.keys())

        expected_subcommands = [
            'summarize', 'keywords', 'classify', 'sentiment',
            'batch-summarize', 'extract-stocks', 'market-summary', 'stocks'
        ]
        for cmd in expected_subcommands:
            assert cmd in subcommand_names, f"子命令 'ai {cmd}' 未注册到 ai group"

    def test_stocks_group_has_all_subcommands(self):
        """测试 stocks group 包含所有子命令。"""
        ai_group = main.commands['ai']
        stocks_group = ai_group.commands['stocks']
        subcommand_names = list(stocks_group.commands.keys())

        expected_subcommands = ['list', 'search', 'show']
        for cmd in expected_subcommands:
            assert cmd in subcommand_names, f"子命令 'ai stocks {cmd}' 未注册到 stocks group"


class TestCLICommandHelpMessages:
    """CLI 命令帮助信息测试。"""

    def test_version_command_help(self):
        """测试 version 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['version', '--help'])
        assert result.exit_code == 0
        assert '版本' in result.output or 'version' in result.output.lower()

    def test_login_command_help(self):
        """测试 login 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['login', '--help'])
        assert result.exit_code == 0
        assert '登录' in result.output or 'login' in result.output.lower()

    def test_subscribe_command_help(self):
        """测试 subscribe 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['subscribe', '--help'])
        assert result.exit_code == 0
        assert '订阅' in result.output or 'subscribe' in result.output.lower()

    def test_fetch_command_help(self):
        """测试 fetch 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['fetch', '--help'])
        assert result.exit_code == 0
        assert '抓取' in result.output or 'fetch' in result.output.lower()
        assert '默认抓取最新 10 条文章' in result.output or '抓取' in result.output

    def test_market_summary_command_help(self):
        """测试 market-summary 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['ai', 'market-summary', '--help'])
        assert result.exit_code == 0
        assert '市场' in result.output or 'market' in result.output.lower()

    def test_extract_stocks_command_help(self):
        """测试 extract-stocks 命令帮助信息。"""
        runner = CliRunner()
        result = runner.invoke(main, ['ai', 'extract-stocks', '--help'])
        assert result.exit_code == 0
        assert '股票' in result.output or 'stock' in result.output.lower()


class TestFetchCommandBehavior:
    """fetch 命令行为测试。"""

    def test_fetch_defaults_to_latest_ten(self):
        """测试 fetch 默认抓取最新 10 条。"""
        runner = CliRunner()
        auth_service = MagicMock()
        auth_service.get_current_token = AsyncMock(return_value="token")
        fetcher_service = MagicMock()
        fetcher_service.fetch_feed = AsyncMock(return_value=[])
        subscription_service = MagicMock()
        subscription_service.get_subscription = AsyncMock(return_value=None)
        rss_service = MagicMock()
        rss_service.list_sources = AsyncMock(return_value=[])

        with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.subscription.AuthService", return_value=auth_service):
                with patch("src.cli.subscription.SubscriptionService", return_value=subscription_service):
                    with patch("src.cli.subscription.FetcherService", return_value=fetcher_service):
                        with patch("src.cli.subscription.RSSSourceService", return_value=rss_service):
                            result = runner.invoke(main, ["fetch", "MP_WXS_test"])

        assert result.exit_code == 0
        assert "抓取范围: 最新 10 条" in result.output
        fetcher_service.fetch_feed.assert_awaited_once_with(
            "MP_WXS_test",
            days=None,
            latest_count=10,
            on_progress=ANY,
        )

    def test_fetch_full_overrides_days(self):
        """测试 --full 优先于 --days。"""
        runner = CliRunner()
        auth_service = MagicMock()
        auth_service.get_current_token = AsyncMock(return_value="token")
        fetcher_service = MagicMock()
        fetcher_service.fetch_feed = AsyncMock(return_value=[])
        subscription_service = MagicMock()
        subscription_service.get_subscription = AsyncMock(return_value=None)
        rss_service = MagicMock()
        rss_service.list_sources = AsyncMock(return_value=[])

        with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=MagicMock())):
            with patch("src.cli.subscription.AuthService", return_value=auth_service):
                with patch("src.cli.subscription.SubscriptionService", return_value=subscription_service):
                    with patch("src.cli.subscription.FetcherService", return_value=fetcher_service):
                        with patch("src.cli.subscription.RSSSourceService", return_value=rss_service):
                            result = runner.invoke(main, ["fetch", "MP_WXS_test", "--days", "30", "--full"])

        assert result.exit_code == 0
        assert "抓取范围: 全部历史" in result.output
        fetcher_service.fetch_feed.assert_awaited_once_with(
            "MP_WXS_test",
            days=None,
            latest_count=None,
            on_progress=ANY,
        )

    def test_subscribe_wechat2rss_does_not_require_login(self):
        """测试 wechat2rss provider 下订阅不要求 weread 登录。"""
        runner = CliRunner()
        auth_service = MagicMock()
        auth_service.get_current_token = AsyncMock(return_value=None)
        fetcher_service = MagicMock()
        fetcher_service.get_mp_info_from_article = AsyncMock(
            return_value={
                "mp_id": "3008522239",
                "name": "e公司",
                "intro": "",
                "cover": "",
                "provider": "wechat2rss",
                "provider_feed_id": "3008522239",
                "provider_meta": "{}",
            }
        )
        subscription_service = MagicMock()
        subscription_service.add_subscription = AsyncMock(return_value=(MagicMock(), True))

        with patch("src.cli.subscription.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(article_list_provider="wechat2rss")
            with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=MagicMock())):
                with patch("src.cli.subscription.AuthService", return_value=auth_service):
                    with patch("src.cli.subscription.SubscriptionService", return_value=subscription_service):
                        with patch("src.cli.subscription.FetcherService", return_value=fetcher_service):
                            result = runner.invoke(main, ["subscribe", "https://mp.weixin.qq.com/s/test"])

        assert result.exit_code == 0
        auth_service.get_current_token.assert_not_awaited()
        subscription_service.add_subscription.assert_awaited_once()

    def test_fetch_wechat2rss_single_feed_skips_login(self):
        """测试 wechat2rss provider 下单号抓取不要求 weread 登录。"""
        runner = CliRunner()
        auth_service = MagicMock()
        auth_service.get_current_token = AsyncMock(return_value=None)
        fetcher_service = MagicMock()
        fetcher_service.fetch_feed = AsyncMock(return_value=[])
        feed = MagicMock(mp_id="3008522239", provider="wechat2rss")
        subscription_service = MagicMock()
        subscription_service.get_subscription = AsyncMock(return_value=feed)
        rss_service = MagicMock()
        rss_service.list_sources = AsyncMock(return_value=[])

        with patch("src.cli.subscription.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(article_list_provider="wechat2rss")
            with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=MagicMock())):
                with patch("src.cli.subscription.AuthService", return_value=auth_service):
                    with patch("src.cli.subscription.SubscriptionService", return_value=subscription_service):
                        with patch("src.cli.subscription.FetcherService", return_value=fetcher_service):
                            with patch("src.cli.subscription.RSSSourceService", return_value=rss_service):
                                result = runner.invoke(main, ["fetch", "3008522239"])

        assert result.exit_code == 0
        auth_service.get_current_token.assert_not_awaited()
