"""export 命令 --all 模式及进度汇总测试。"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from src.cli import main
from src.cli.article import (
    ExportSummary,
    _export_feed_articles,
    _print_summary_line,
)
from src.models.schema import Article, Feed


def _make_feed(
    mp_id: str = "biz:test_mp",
    name: str = "测试公众号",
    feed_id: int = 1,
) -> Feed:
    """构造测试用 Feed 对象。"""
    feed = MagicMock(spec=Feed)
    feed.id = feed_id
    feed.mp_id = mp_id
    feed.name = name
    feed.status = 1
    return feed


def _make_article(
    article_id: int = 1,
    title: str = "测试文章",
    feed_id: int = 1,
    publish_time: datetime | None = None,
) -> Article:
    """构造测试用 Article 对象。"""
    return Article(
        id=article_id,
        article_id=f"art_{article_id}",
        title=title,
        content=f"<p>{title} 正文内容</p>",
        feed_id=feed_id,
        publish_time=publish_time or datetime(2024, 6, 15, 10, 0),
    )


class TestExportValidation:
    """export 命令参数校验测试。"""

    def test_no_mp_id_no_all_shows_usage_error(self) -> None:
        """不指定 MP_ID 也不指定 --all 应报错并提示用法。"""
        runner = CliRunner()
        result = runner.invoke(main, ["export"])
        assert result.exit_code == 0
        assert "请指定公众号 ID 或使用 --all" in result.output
        assert "wchat export" in result.output

    def test_mp_id_and_all_conflict(self) -> None:
        """同时指定 MP_ID 和 --all 应报冲突错误。"""
        runner = CliRunner()
        result = runner.invoke(main, ["export", "biz:test_mp", "--all"])
        assert result.exit_code == 0
        assert "不能同时指定公众号 ID 和 --all" in result.output
        assert "wchat export" in result.output


class TestExportAllNoActiveFeeds:
    """export --all 无活跃订阅测试。"""

    def test_no_active_feeds_shows_message(self) -> None:
        """没有活跃订阅时应提示信息。"""
        runner = CliRunner()

        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=False)))

        with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
            result = runner.invoke(main, ["export", "--all"])

        assert result.exit_code == 0
        assert "没有活跃的订阅" in result.output


class TestExportAllMultipleFeeds:
    """export --all 多订阅导出测试。"""

    def test_exports_multiple_active_feeds(self) -> None:
        """应导出所有活跃订阅的文章。"""
        feed1 = _make_feed(mp_id="biz:feed1", name="公众号A", feed_id=1)
        feed2 = _make_feed(mp_id="biz:feed2", name="公众号B", feed_id=2)

        articles1 = [_make_article(article_id=i, title=f"文章A-{i}", feed_id=1) for i in range(1, 4)]
        articles2 = [_make_article(article_id=i, title=f"文章B-{i}", feed_id=2) for i in range(4, 7)]

        call_count = 0

        async def _mock_session_execute(query):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            if call_count == 1:
                # 第一次调用：查询所有活跃 feeds
                result_mock.scalars.return_value.all.return_value = [feed1, feed2]
            elif call_count == 2:
                # 第二次调用：查询 feed1 的文章
                result_mock.scalars.return_value.all.return_value = articles1
            else:
                # 第三次调用：查询 feed2 的文章
                result_mock.scalars.return_value.all.return_value = articles2
            return result_mock

        session = MagicMock()
        session.execute = _mock_session_execute

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            try:
                with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
                    runner = CliRunner()
                    result = runner.invoke(main, ["export", "--all"])

                assert result.exit_code == 0
                # 应显示批量导出头
                assert "批量导出: 2 个公众号" in result.output
                assert "模式: 增量" in result.output
                assert "格式: HTML" in result.output

                # 应显示进度标记
                assert "[1/2]" in result.output
                assert "[2/2]" in result.output

                # 应显示总计
                assert "总计" in result.output
                assert "公众号: 2" in result.output
                assert "新导出: 6" in result.output
                assert "文章总数: 6" in result.output
            finally:
                article_module.EXPORT_BASE_DIR = original_base


class TestExportAllForce:
    """export --all --force 测试。"""

    def test_force_rebuilds_per_feed_directories(self) -> None:
        """--all --force 应逐个清除并重建每个公众号的导出目录。"""
        feed = _make_feed(mp_id="biz:force_feed", name="重建测试", feed_id=1)
        articles = [_make_article(article_id=i, title=f"文章-{i}", feed_id=1) for i in range(1, 3)]

        call_count = 0

        async def _mock_session_execute(query):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            if call_count == 1:
                result_mock.scalars.return_value.all.return_value = [feed]
            else:
                result_mock.scalars.return_value.all.return_value = articles
            return result_mock

        session = MagicMock()
        session.execute = _mock_session_execute

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            # 创建旧文件
            feed_dir = Path(tmpdir) / "export_articles" / "biz:force_feed"
            feed_dir.mkdir(parents=True)
            (feed_dir / "old_file.html").write_text("old content")

            try:
                with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
                    runner = CliRunner()
                    result = runner.invoke(main, ["export", "--all", "--force"])

                assert result.exit_code == 0
                assert "模式: 强制重建" in result.output

                # 旧文件应已被清除
                assert not (feed_dir / "old_file.html").exists()

                # 新文件应已生成
                html_files = list(feed_dir.glob("*.html"))
                assert len(html_files) == 2
            finally:
                article_module.EXPORT_BASE_DIR = original_base


class TestExportSingleSummary:
    """单账号导出汇总输出测试。"""

    def test_single_account_start_output(self) -> None:
        """单账号导出应显示名称、mp_id、模式、格式、输出目录。"""
        feed = _make_feed(mp_id="biz:single_test", name="单号测试", feed_id=1)
        articles = [_make_article(article_id=1, title="文章1", feed_id=1)]

        session = MagicMock()

        async def _mock_session_execute(query):
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = feed
            result_mock.scalars.return_value.all.return_value = articles
            return result_mock

        session.execute = _mock_session_execute

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            try:
                with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
                    runner = CliRunner()
                    result = runner.invoke(main, ["export", "biz:single_test"])

                assert result.exit_code == 0
                assert "单号测试" in result.output
                assert "biz:single_test" in result.output
                assert "模式: 增量" in result.output
                assert "格式: HTML" in result.output
                assert "输出目录" in result.output
                assert "新导出: 1" in result.output
            finally:
                article_module.EXPORT_BASE_DIR = original_base

    def test_no_new_articles_output(self) -> None:
        """增量导出零新文章时应提示没有新文章。"""
        feed = _make_feed(mp_id="biz:no_new", name="无新文章号", feed_id=1)
        articles = [_make_article(article_id=1, title="已存在文章", feed_id=1)]

        session = MagicMock()

        async def _mock_session_execute(query):
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = feed
            result_mock.scalars.return_value.all.return_value = articles
            return result_mock

        session.execute = _mock_session_execute

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            # 预创建已存在文件
            export_dir = Path(tmpdir) / "export_articles" / "biz:no_new"
            export_dir.mkdir(parents=True)
            (export_dir / "2024-06-15_已存在文章.html").write_text("existing")

            try:
                with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
                    runner = CliRunner()
                    result = runner.invoke(main, ["export", "biz:no_new"])

                assert result.exit_code == 0
                assert "没有新文章需要导出" in result.output
                assert "已存在跳过: 1" in result.output
            finally:
                article_module.EXPORT_BASE_DIR = original_base


class TestExportFeedArticlesFailure:
    """单篇文章写入失败测试。"""

    def test_write_failure_increments_failed_and_continues(self) -> None:
        """单篇文章写入失败应记录失败数并继续。"""
        feed = _make_feed(mp_id="biz:fail_test", name="失败测试", feed_id=1)
        articles = [
            _make_article(article_id=1, title="好文章", feed_id=1),
            _make_article(article_id=2, title="坏文章", feed_id=1),
            _make_article(article_id=3, title="另一好文章", feed_id=1),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            try:
                # 让第二篇文章写入失败
                original_write = Path.write_text
                call_count = 0

                def _failing_write(self, content, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 2:
                        raise OSError("模拟写入失败")
                    return original_write(self, content, **kwargs)

                with patch.object(Path, "write_text", _failing_write):
                    summary = _export_feed_articles(feed, articles, force=False)

                assert summary.total == 3
                assert summary.failed == 1
                assert summary.exported == 2
                assert summary.skipped == 0
            finally:
                article_module.EXPORT_BASE_DIR = original_base


class TestExportSummaryUnit:
    """ExportSummary 单元测试。"""

    def test_summary_fields(self) -> None:
        """ExportSummary 应包含所有必要字段。"""
        summary = ExportSummary(
            feed_name="测试号",
            mp_id="biz:test",
            output_dir=Path("/tmp/export"),
            exported=10,
            skipped=5,
            failed=1,
            total=16,
        )
        assert summary.feed_name == "测试号"
        assert summary.mp_id == "biz:test"
        assert summary.exported == 10
        assert summary.skipped == 5
        assert summary.failed == 1
        assert summary.total == 16

    def test_summary_defaults(self) -> None:
        """ExportSummary 计数默认应为 0。"""
        summary = ExportSummary(
            feed_name="默认号",
            mp_id="biz:default",
            output_dir=Path("/tmp/export"),
        )
        assert summary.exported == 0
        assert summary.skipped == 0
        assert summary.failed == 0
        assert summary.total == 0

    def test_print_summary_highlights_failures(self) -> None:
        """非零失败数应以红色高亮显示。"""
        import re

        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)

        summary = ExportSummary(
            feed_name="失败号",
            mp_id="biz:fail",
            output_dir=Path("/tmp/export"),
            exported=5,
            skipped=2,
            failed=3,
            total=10,
        )

        with patch("src.cli.article.console", console):
            _print_summary_line(summary)

        output = buf.getvalue()
        # 剥离 ANSI 转义码后检查内容
        clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
        assert "失败: 3" in clean
        # 原始输出应包含红色 ANSI 转义码（31=red）
        assert "\x1b[1;31m" in output

    def test_print_summary_zero_failures_no_red(self) -> None:
        """零失败数不应使用红色高亮。"""
        import re

        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)

        summary = ExportSummary(
            feed_name="无失败号",
            mp_id="biz:ok",
            output_dir=Path("/tmp/export"),
            exported=5,
            skipped=2,
            failed=0,
            total=7,
        )

        with patch("src.cli.article.console", console):
            _print_summary_line(summary)

        output = buf.getvalue()
        clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
        assert "失败: 0" in clean
        # 零失败不应使用红色（31）转义码
        assert "\x1b[1;31m" not in output


class TestExportAllAggregateSummary:
    """--all 聚合汇总测试。"""

    def test_aggregate_summary_includes_all_totals(self) -> None:
        """聚合汇总应包含所有公众号和文章的合计。"""
        feed1 = _make_feed(mp_id="biz:agg1", name="合计A", feed_id=1)
        feed2 = _make_feed(mp_id="biz:agg2", name="合计B", feed_id=2)

        articles1 = [_make_article(article_id=i, title=f"A-{i}", feed_id=1) for i in range(1, 3)]
        articles2 = [_make_article(article_id=i, title=f"B-{i}", feed_id=2) for i in range(3, 5)]

        call_count = 0

        async def _mock_session_execute(query):
            nonlocal call_count
            call_count += 1
            result_mock = MagicMock()
            if call_count == 1:
                result_mock.scalars.return_value.all.return_value = [feed1, feed2]
            elif call_count == 2:
                result_mock.scalars.return_value.all.return_value = articles1
            else:
                result_mock.scalars.return_value.all.return_value = articles2
            return result_mock

        session = MagicMock()
        session.execute = _mock_session_execute

        db = MagicMock()
        db.get_session = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=session),
            __aexit__=AsyncMock(return_value=False),
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.cli import article as article_module

            original_base = article_module.EXPORT_BASE_DIR
            article_module.EXPORT_BASE_DIR = Path(tmpdir) / "export_articles"

            try:
                with patch("src.cli.article.get_db", new=AsyncMock(return_value=db)):
                    runner = CliRunner()
                    result = runner.invoke(main, ["export", "--all"])

                assert result.exit_code == 0
                assert "公众号: 2" in result.output
                assert "新导出: 4" in result.output
                assert "文章总数: 4" in result.output
                assert "已存在跳过: 0" in result.output
                assert "失败: 0" in result.output
            finally:
                article_module.EXPORT_BASE_DIR = original_base
