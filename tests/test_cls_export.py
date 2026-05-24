"""CLS export 命令和 HTML 渲染测试。"""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import main
from src.cli.cls_export import (
    CLSExportResult,
    build_cls_export_html,
    build_cls_export_path,
    date_window,
    parse_json_field,
    write_export,
)


# ---------------------------------------------------------------------------
# 6.1 Default current-date export
# ---------------------------------------------------------------------------


class TestExportDefaultDate:
    """默认当前日期导出测试。"""

    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_default_exports_today(
        self, mock_get_db, mock_telegraphs, mock_watch, tmp_path
    ):
        mock_get_db.return_value = AsyncMock()
        mock_telegraphs.return_value = []
        mock_watch.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export'])
        assert result.exit_code == 0
        assert "无匹配数据" in result.output


# ---------------------------------------------------------------------------
# 6.2 Specified date export
# ---------------------------------------------------------------------------


class TestExportSpecifiedDate:
    """指定日期导出测试。"""

    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_specified_date(
        self, mock_get_db, mock_telegraphs, mock_watch, tmp_path
    ):
        mock_get_db.return_value = AsyncMock()
        mock_telegraphs.return_value = []
        mock_watch.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--date', '2026-05-20'])
        assert result.exit_code == 0
        assert "2026-05-20" in result.output

    def test_invalid_date_format(self):
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--date', 'not-a-date'])
        assert result.exit_code == 0
        assert "日期格式错误" in result.output


# ---------------------------------------------------------------------------
# 6.3 --all daily file generation
# ---------------------------------------------------------------------------


class TestExportAll:
    """--all 批量导出测试。"""

    @patch('src.cli.cls_data.discover_local_dates', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_all_no_dates(self, mock_get_db, mock_discover):
        mock_get_db.return_value = AsyncMock()
        mock_discover.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--all'])
        assert result.exit_code == 0
        assert "无匹配" in result.output

    @patch('src.cli.cls_data.write_export')
    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.discover_local_dates', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_all_with_dates(
        self, mock_get_db, mock_discover, mock_telegraphs, mock_watch, mock_write
    ):
        mock_get_db.return_value = AsyncMock()
        mock_discover.return_value = [date(2026, 5, 20), date(2026, 5, 21)]

        # Mock telegraph data for first date, none for second
        telegraph_mock = MagicMock()
        telegraph_mock.ctime = int(datetime(2026, 5, 20, 10, 0, 0).timestamp())
        telegraph_mock.level = "A"
        telegraph_mock.title = "测试电报"
        telegraph_mock.content = "内容"

        mock_telegraphs.side_effect = [[telegraph_mock], []]
        mock_watch.side_effect = [[], []]
        mock_write.return_value = True

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--all'])
        assert result.exit_code == 0
        assert "2 个日期" in result.output
        assert "总计" in result.output


# ---------------------------------------------------------------------------
# 6.4 --type telegraphs, --type watch, --type all
# ---------------------------------------------------------------------------


class TestExportType:
    """--type 类型选择测试。"""

    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_type_telegraphs(self, mock_get_db, mock_telegraphs, mock_watch):
        mock_get_db.return_value = AsyncMock()
        mock_telegraphs.return_value = []
        mock_watch.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--type', 'telegraphs'])
        assert result.exit_code == 0
        assert "telegraphs" in result.output

    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_type_watch(self, mock_get_db, mock_telegraphs, mock_watch):
        mock_get_db.return_value = AsyncMock()
        mock_telegraphs.return_value = []
        mock_watch.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--type', 'watch'])
        assert result.exit_code == 0
        assert "watch" in result.output

    @patch('src.cli.cls_data.query_watch_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.query_telegraphs_for_date', new_callable=AsyncMock)
    @patch('src.cli.cls_data.get_db', new_callable=AsyncMock)
    def test_type_all(self, mock_get_db, mock_telegraphs, mock_watch):
        mock_get_db.return_value = AsyncMock()
        mock_telegraphs.return_value = []
        mock_watch.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--type', 'all'])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 6.5 Existing-file skip and --force overwrite
# ---------------------------------------------------------------------------


class TestIncrementality:
    """增量跳过和 --force 测试。"""


    def test_skip_existing_file(self, tmp_path):
        target = tmp_path / "2026-05-20.html"
        target.write_text("old content", encoding="utf-8")

        written = write_export(target, "new content", force=False)
        assert not written
        assert target.read_text(encoding="utf-8") == "old content"

    def test_force_overwrites_existing(self, tmp_path):
        target = tmp_path / "2026-05-20.html"
        target.write_text("old content", encoding="utf-8")

        written = write_export(target, "new content", force=True)
        assert written
        assert target.read_text(encoding="utf-8") == "new content"

    def test_writes_new_file(self, tmp_path):
        target = tmp_path / "subdir" / "2026-05-20.html"

        written = write_export(target, "new content", force=False)
        assert written
        assert target.read_text(encoding="utf-8") == "new content"


# ---------------------------------------------------------------------------
# 6.6 Validation tests for invalid option combinations
# ---------------------------------------------------------------------------


class TestExportValidation:
    """参数校验测试。"""

    def test_date_and_all_conflict(self):
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--date', '2026-05-20', '--all'])
        assert result.exit_code == 0
        assert "不能同时指定" in result.output

    def test_output_and_all_conflict(self):
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--all', '--output', 'out.html'])
        assert result.exit_code == 0
        assert "--output 不能与 --all" in result.output

    def test_export_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ['cls', 'export', '--help'])
        assert result.exit_code == 0
        assert 'export' in result.output.lower() or '导出' in result.output


# ---------------------------------------------------------------------------
# 6.7 HTML rendering tests
# ---------------------------------------------------------------------------


class TestHTMLRendering:
    """HTML 渲染测试。"""

    def test_full_document_structure(self):
        html = build_cls_export_html(
            date(2026, 5, 20), "all", [], [], "2026-05-20 12:00:00"
        )
        assert "<!doctype html>" in html
        assert '<html lang="zh-CN">' in html
        assert '<meta charset="utf-8">' in html
        assert "viewport" in html
        assert "<style>" in html

    def test_overview_counts(self):
        telegraphs = [MagicMock(ctime=0, level="A", title="T", content="C")]
        watches = [MagicMock(ctime=0, data_type="hot", title="W", content="",
                             stocks=None, sectors=None)]

        html = build_cls_export_html(
            date(2026, 5, 20), "all", telegraphs, watches, "12:00:00"
        )
        assert ">1<" in html  # count
        assert "电报" in html
        assert "看盘" in html

    def test_telegraph_level_badges(self):
        telegraph = MagicMock()
        telegraph.ctime = int(datetime(2026, 5, 20, 10, 0, 0).timestamp())
        telegraph.level = "A"
        telegraph.title = "重要电报"
        telegraph.content = "内容"

        html = build_cls_export_html(
            date(2026, 5, 20), "telegraphs", [telegraph], [], "12:00"
        )
        assert "badge-a" in html
        assert "A级" in html
        assert "重要电报" in html

    def test_watch_stocks_sectors_tags(self):
        watch = MagicMock()
        watch.ctime = int(datetime(2026, 5, 20, 14, 0, 0).timestamp())
        watch.data_type = "stock_comment"
        watch.title = "个股点评"
        watch.content = "内容"
        watch.stocks = json.dumps(["贵州茅台", "五粮液"])
        watch.sectors = json.dumps(["白酒"])

        html = build_cls_export_html(
            date(2026, 5, 20), "watch", [], [watch], "12:00"
        )
        assert "贵州茅台" in html
        assert "白酒" in html
        assert "stock_comment" in html
        assert "tag" in html

    def test_html_escaping(self):
        telegraph = MagicMock()
        telegraph.ctime = 0
        telegraph.level = "C"
        telegraph.title = "<script>alert('xss')</script>"
        telegraph.content = "a & b < c > d"

        html = build_cls_export_html(
            date(2026, 5, 20), "telegraphs", [telegraph], [], "12:00"
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp;" in html

    def test_no_data_placeholder_when_other_has_data(self):
        telegraph = MagicMock()
        telegraph.ctime = 0
        telegraph.level = "A"
        telegraph.title = "T"
        telegraph.content = "C"

        # type=all, telegraphs has data but watch is empty
        html = build_cls_export_html(
            date(2026, 5, 20), "all", [telegraph], [], "12:00"
        )
        assert "无看盘数据" in html

    def test_no_data_placeholder_telegraphs_empty(self):
        watch = MagicMock()
        watch.ctime = 0
        watch.data_type = "hot"
        watch.title = "W"
        watch.content = ""
        watch.stocks = None
        watch.sectors = None

        html = build_cls_export_html(
            date(2026, 5, 20), "all", [], [watch], "12:00"
        )
        assert "无电报数据" in html

    def test_no_placeholder_when_type_is_single(self):
        # type=telegraphs, no data - should not show watch placeholder
        html = build_cls_export_html(
            date(2026, 5, 20), "telegraphs", [], [], "12:00"
        )
        assert "无看盘数据" not in html

    def test_line_breaks_preserved(self):
        telegraph = MagicMock()
        telegraph.ctime = 0
        telegraph.level = "C"
        telegraph.title = "标题"
        telegraph.content = "第一行\n第二行"

        html = build_cls_export_html(
            date(2026, 5, 20), "telegraphs", [telegraph], [], "12:00"
        )
        assert "第一行<br>第二行" in html


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestDateWindow:
    """date_window 辅助函数测试。"""

    def test_returns_timestamps(self):
        start, end = date_window(date(2026, 5, 20))
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert start < end

    def test_midnight_to_end_of_day(self):
        start, end = date_window(date(2026, 5, 20))
        start_dt = datetime.fromtimestamp(start)
        end_dt = datetime.fromtimestamp(end)
        assert start_dt.hour == 0 and start_dt.minute == 0
        assert end_dt.hour == 23 and end_dt.minute == 59


class TestBuildExportPath:
    """build_cls_export_path 路径生成测试。"""

    def test_all_type(self):
        path = build_cls_export_path(date(2026, 5, 20), "all")
        assert str(path) == "output/cls_exports/2026-05-20.html"

    def test_telegraphs_type(self):
        path = build_cls_export_path(date(2026, 5, 20), "telegraphs")
        assert str(path) == "output/cls_exports/2026-05-20_telegraphs.html"

    def test_watch_type(self):
        path = build_cls_export_path(date(2026, 5, 20), "watch")
        assert str(path) == "output/cls_exports/2026-05-20_watch.html"


class TestParseJsonField:
    """parse_json_field JSON 解析测试。"""

    def test_valid_list(self):
        assert parse_json_field('["a", "b"]') == ["a", "b"]

    def test_none(self):
        assert parse_json_field(None) == []

    def test_empty_string(self):
        assert parse_json_field("") == []

    def test_invalid_json(self):
        assert parse_json_field("not json") == []

    def test_non_list(self):
        assert parse_json_field('{"key": "val"}') == []


class TestCLSExportResult:
    """CLSExportResult 数据类测试。"""

    def test_defaults(self):
        r = CLSExportResult(
            target_date=date(2026, 5, 20),
            export_type="all",
            output_path=Path("out.html"),
        )
        assert r.telegraph_count == 0
        assert r.watch_count == 0
        assert r.exported is False
        assert r.skipped is False
        assert r.no_data is False
