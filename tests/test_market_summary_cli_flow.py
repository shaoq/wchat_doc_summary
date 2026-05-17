"""market-summary CLI 流程测试。"""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from src.cli import main


def _global_context(status="ok"):
    return {
        "status": status,
        "target_a_trade_date": "2026-03-27",
        "captured_at": "2026-03-27T22:30:00+08:00",
        "as_of": "2026-03-27T22:29:00+08:00" if status != "error" else None,
        "session": "regular" if status != "error" else None,
        "source": "yahoo_quote",
        "message": "海外市场上下文获取完成" if status != "error" else "海外市场上下文不可用",
        "us_market": {
            "status": status,
            "session": "regular" if status != "error" else None,
            "as_of": "2026-03-27T22:29:00+08:00" if status != "error" else None,
            "indices": [
                {"symbol": "DJIA", "name": "道琼斯工业平均指数", "price": 39000.0, "change_pct": 0.004},
                {"symbol": "SPX", "name": "标普500", "price": 5200.0, "change_pct": 0.006},
                {"symbol": "IXIC", "name": "纳斯达克综合指数", "price": 16500.0, "change_pct": 0.009},
            ] if status != "error" else [],
            "risk_signals": {},
            "leaders": [],
            "source": "yahoo_quote",
        },
    }


class _FakeAnalyzer:
    """可记录调用参数的 MarketAnalyzer 替身。"""

    instances: list["_FakeAnalyzer"] = []

    def __init__(self, db):
        self.db = db
        self.collect_market_data_calls = []
        self.collect_news_data_calls = []
        self.list_summaries_calls = []
        self.get_existing_summary_calls = []
        _FakeAnalyzer.instances.append(self)

    def get_latest_trade_date(self):
        return date(2026, 3, 27)

    async def list_summaries(self, limit=10):
        self.list_summaries_calls.append({"limit": limit})
        return []

    async def get_existing_summary(self, trade_date):
        self.get_existing_summary_calls.append(trade_date)
        return None

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {},
            "limit_up": [],
            "global_market_context": _global_context(),
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
        }

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "success",
            "telegraphs": [],
            "watch_items": [],
            "articles": [],
            "sources_status": {
                "telegraphs": "empty",
                "watch_items": "empty",
                "articles": "empty",
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }

    async def save_summary(self, trade_date, content, market_data, **kwargs):
        return None


class _OfflineNoCacheAnalyzer(_FakeAnalyzer):
    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "offline": True,
            "data_source": "none",
            "error": "离线模式: 无可用本地市场数据",
        }


class _HistoricalNoDataAnalyzer(_FakeAnalyzer):
    """历史交易日无缓存的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "none",
            "error": "历史交易日 2026-03-20 无可用市场数据（无缓存且无历史数据源）",
        }


class _OnlineFetchErrorAnalyzer(_FakeAnalyzer):
    """在线抓取失败的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "error",
            "error": "ConnectionError: 获取在线数据失败",
        }


class _RawPayloadAnalyzer(_FakeAnalyzer):
    """返回带 raw adapter 痕迹的 market_data，用于验证 CLI 不泄漏底层结构。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {
                "sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045},
            },
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "source_debug": {"RAW_PAYLOAD_MARKER": {"diff": [{"unexpected_raw_field": "value"}]}},
        }


class _ListAnalyzer(_FakeAnalyzer):
    async def list_summaries(self, limit=10):
        self.list_summaries_calls.append({"limit": limit})
        return [
            SimpleNamespace(
                trade_date=date(2026, 3, 26),
                created_at=datetime(2026, 3, 26, 18, 30),
            )
        ]


class _FakeProcessor:
    """AIProcessor 替身。"""

    instances: list["_FakeProcessor"] = []

    def __init__(self, db):
        self.db = db
        self.generate_calls = []
        _FakeProcessor.instances.append(self)

    async def generate_market_summary(self, **kwargs):
        self.generate_calls.append(kwargs)
        return "测试总结内容"


class _FakeProcessorThatFailsInit:
    """初始化就会抛出 ValueError 的 AIProcessor 替身（模拟无 LLM 配置）。"""

    instances: list["_FakeProcessorThatFailsInit"] = []

    def __init__(self, db):
        _FakeProcessorThatFailsInit.instances.append(self)
        raise ValueError("LLM API Key 未配置，请设置 LLM_API_KEY")

    async def generate_market_summary(self, **kwargs):
        return "不应到达这里"


async def _fake_get_db():
    return object()


class _PartialMarketDataAnalyzer(_FakeAnalyzer):
    """返回部分成功、部分失败的市场数据，用于验证逐项状态展示。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {
                "sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045},
                "sz": {"name": "深证成指", "close": 9876.54, "change": -0.0032},
            },
            "volume": {},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "global_market_context": _global_context(),
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
        }


# ---------------------------------------------------------------------------
# 基础功能测试
# ---------------------------------------------------------------------------


def test_market_summary_passes_date_and_force_to_collect_market_data():
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-21", "--force"],
                )

    assert result.exit_code == 0
    analyzer = _FakeAnalyzer.instances[0]
    assert analyzer.collect_market_data_calls[0]["trade_date"] == date(2026, 3, 21)
    assert analyzer.collect_market_data_calls[0]["force"] is True


def test_market_summary_offline_without_cache_stops_before_ai_generation():
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _OfflineNoCacheAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(main, ["ai", "market-summary", "--offline"])

    assert result.exit_code == 0
    assert "离线模式: 无可用本地市场数据" in result.output
    analyzer = _FakeAnalyzer.instances[0]
    assert analyzer.collect_news_data_calls == []
    processor = _FakeProcessor.instances[0]
    assert processor.generate_calls == []


def test_market_summary_historical_no_data_stops_before_ai_generation():
    """历史交易日无缓存时，CLI 应停止在数据获取阶段。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _HistoricalNoDataAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-20"],
                )

    assert result.exit_code == 0
    assert "历史交易日" in result.output
    analyzer = _FakeAnalyzer.instances[0]
    assert analyzer.collect_news_data_calls == []
    processor = _FakeProcessor.instances[0]
    assert processor.generate_calls == []


def test_stage1_output_does_not_leak_raw_source_payload():
    """stage 1 输出不应暴露 adapter/raw payload 结构。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _RawPayloadAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert result.exit_code == 0
    assert "RAW_PAYLOAD_MARKER" not in result.output
    assert "unexpected_raw_field" not in result.output


def test_market_summary_online_fetch_error_stops_before_ai_generation():
    """在线抓取失败时，CLI 应停止在数据获取阶段。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _OnlineFetchErrorAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert result.exit_code == 0
    assert "市场数据不可用" in result.output
    analyzer = _FakeAnalyzer.instances[0]
    assert analyzer.collect_news_data_calls == []
    processor = _FakeProcessor.instances[0]
    assert processor.generate_calls == []


def test_market_summary_list_uses_created_at():
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _ListAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(main, ["ai", "market-summary", "--list"])

    assert result.exit_code == 0
    assert "2026-03-26" in result.output
    assert "18:30" in result.output


def test_market_summary_list_works_without_llm_config():
    """--list 分支不应初始化 AIProcessor，即使 LLM 未配置也应正常工作。"""
    runner = CliRunner()
    _ListAnalyzer.instances = []
    _FakeProcessorThatFailsInit.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _ListAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessorThatFailsInit):
                result = runner.invoke(main, ["ai", "market-summary", "--list"])

    assert result.exit_code == 0
    assert "2026-03-26" in result.output
    # AIProcessor 不应被初始化（因为是 --list 分支）
    assert len(_FakeProcessorThatFailsInit.instances) == 0


# ---------------------------------------------------------------------------
# Task 2.1: 成功路径 — 三阶段标题按顺序出现
# ---------------------------------------------------------------------------


def test_successful_run_shows_ordered_stage_conclusions():
    """成功路径下，三阶段结论应按顺序出现。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    # 三个阶段都应有结论行
    idx_market = output.find("指数:")
    idx_news = output.find("新闻数据获取完成")
    idx_ai = output.find("生成并保存完成")

    assert idx_market > 0, f"缺少市场数据阶段结论, output={output!r}"
    assert idx_news > 0, f"缺少新闻数据阶段结论, output={output!r}"
    assert idx_ai > 0, f"缺少 AI 生成阶段结论, output={output!r}"

    # 顺序约束：市场 < 新闻 < AI
    assert idx_market < idx_news < idx_ai, "阶段结论顺序不正确"


# ---------------------------------------------------------------------------
# Task 2.2: 失败与离线路径
# ---------------------------------------------------------------------------


def test_market_data_failure_does_not_show_later_stages():
    """阶段 1 失败时，不应出现阶段 2/3 的结论。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _OnlineFetchErrorAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert "新闻数据获取完成" not in output, "失败后不应出现阶段 2 结论"
    assert "生成并保存完成" not in output, "失败后不应出现阶段 3 结论"


def test_offline_no_cache_shows_offline_label():
    """离线无缓存时，应展示离线模式标签和执行上下文。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _OfflineNoCacheAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(main, ["ai", "market-summary", "--offline"])

    assert "离线模式" in result.output
    assert "执行模式: 离线" in result.output
    assert "仅使用本地数据" in result.output


# ---------------------------------------------------------------------------
# Task 2.3: 新闻资料摘要 — 来源统计与时间窗口顺序
# ---------------------------------------------------------------------------


def test_source_summary_stable_order():
    """来源统计应按固定顺序展示：电报 → 看盘 → 文章。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    idx_telegraph = output.find("财联社电报")
    idx_watch = output.find("看盘数据")
    idx_article = output.find("相关文章")

    assert idx_telegraph > 0, "缺少财联社电报来源"
    assert idx_watch > 0, "缺少看盘数据来源"
    assert idx_article > 0, "缺少相关文章来源"
    assert idx_telegraph < idx_watch < idx_article, "来源顺序应为电报→看盘→文章"


def test_time_windows_stable_order():
    """时间窗口应按固定顺序展示：看盘 → 电报 → 文章。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    idx_watch = output.find("看盘窗口")
    idx_telegraph = output.find("电报窗口")
    idx_article = output.find("文章窗口")

    assert idx_watch > 0, "缺少看盘窗口"
    assert idx_telegraph > 0, "缺少电报窗口"
    assert idx_article > 0, "缺少文章窗口"
    assert idx_watch < idx_telegraph < idx_article, "窗口顺序应为看盘→电报→文章"


def test_empty_sources_preserve_structure():
    """所有来源为空时，输出结构仍保持稳定。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    # 即使数据为空，统计行仍应存在
    assert "财联社电报: 0 条" in output
    assert "看盘数据: 0 条" in output
    assert "相关文章: 0 篇" in output
    # 窗口行仍应存在
    assert "看盘窗口" in output
    assert "电报窗口" in output
    assert "文章窗口" in output


def test_shows_source_specific_windows():
    """CLI 应分别展示看盘、电报、文章的时间窗口。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert result.exit_code == 0
    assert "看盘窗口" in result.output
    assert "电报窗口" in result.output
    assert "文章窗口" in result.output


# ---------------------------------------------------------------------------
# Execution context and persistent stage headers
# ---------------------------------------------------------------------------


def test_execution_context_shows_trade_date_and_mode():
    """执行上下文应展示交易日和执行模式。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert "交易日: 2026-03-27" in output
    assert "执行模式: 强制刷新" in output
    assert "数据策略: 跳过缓存，强制刷新" in output


def test_execution_context_online_mode():
    """在线模式应正确展示执行上下文。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27"],
                )

    output = result.output
    assert "执行模式: 在线" in output
    assert "数据策略: 优先使用缓存" in output


def test_persistent_stage_headers_appear_in_order():
    """持久阶段标题应按顺序出现。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    idx_1 = output.find("[1/3] 获取市场数据")
    idx_2 = output.find("[2/3] 获取新闻数据")
    idx_3 = output.find("[3/3] 生成并保存市场总结")

    assert idx_1 > 0, f"缺少阶段 1 标题, output={output!r}"
    assert idx_2 > 0, f"缺少阶段 2 标题, output={output!r}"
    assert idx_3 > 0, f"缺少阶段 3 标题, output={output!r}"
    assert idx_1 < idx_2 < idx_3, "阶段标题顺序不正确"


def test_data_source_label_displayed():
    """阶段 1 应展示数据来源标签。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert "数据来源: API 实时数据" in result.output


class _BreadthPrimarySourceAnalyzer(_FakeAnalyzer):
    """宽度数据命中官方成交额 + pytdx 主源的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
                "statistics": {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
            },
        }


class _BreadthFallbackSourceAnalyzer(_FakeAnalyzer):
    """成交额命中旧链路兜底、涨跌统计命中 pytdx 的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "akshare_spot_em", "actual_count": 5518, "expected_count": 5518},
                "statistics": {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
            },
        }


def test_breadth_primary_source_label_displayed():
    """阶段 1 应展示官方成交额 + pytdx 宽度标签。"""
    runner = CliRunner()
    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthPrimarySourceAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert "宽度来源: 官方成交额 + pytdx 统计" in result.output


def test_breadth_fallback_source_label_displayed():
    """阶段 1 应展示成交额旧链路兜底 + pytdx 宽度标签。"""
    runner = CliRunner()
    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthFallbackSourceAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert "宽度来源: 成交额旧链路兜底 + pytdx 统计" in result.output


def test_market_stage_shows_component_level_statuses():
    """阶段 1 应在进入生成前展示市场数据逐项状态。"""
    runner = CliRunner()
    _PartialMarketDataAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _PartialMarketDataAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "指数: 已获取 2 个指数" in output
    assert "成交额: 获取失败" in output
    assert "涨跌统计: 已获取 2500/1800/200" in output
    assert "板块: 暂无板块数据" in output
    assert "涨停股: 0 只" in output
    assert "海外市场: DJIA +0.40%, SPX +0.60%, IXIC +0.90%" in output
    assert "session=regular" in output

    idx_stage1 = output.find("[1/3] 获取市场数据")
    idx_indices = output.find("指数: 已获取 2 个指数")
    idx_global = output.find("海外市场:")
    idx_stage2 = output.find("[2/3] 获取新闻数据")
    assert idx_stage1 < idx_indices < idx_stage2, "市场数据逐项状态应位于阶段 1 与阶段 2 之间"
    assert idx_indices < idx_global < idx_stage2, "海外市场状态应位于阶段 1 与阶段 2 之间"


def test_market_summary_passes_global_context_to_processor():
    """AI 生成调用应收到独立的海外市场上下文参数。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert result.exit_code == 0
    call = _FakeProcessor.instances[0].generate_calls[0]
    assert call["global_market_context"]["status"] == "ok"
    assert call["global_market_context"]["us_market"]["indices"][2]["symbol"] == "IXIC"


def test_save_path_in_stage_three():
    """保存路径应在阶段 3 结论块内展示。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    # 保存路径应在阶段 3 标题之后
    idx_stage3 = output.find("[3/3] 生成并保存市场总结")
    idx_save = output.find("已保存到: output/market_summaries/2026-03-27.md")
    assert idx_stage3 > 0, "缺少阶段 3 标题"
    assert idx_save > idx_stage3, "保存路径应在阶段 3 标题之后"


# ---------------------------------------------------------------------------
# Task 1.2: 本地前置校验在 AIProcessor 初始化之前完成
# ---------------------------------------------------------------------------


def test_invalid_date_exits_before_ai_processor_init():
    """无效日期应在 AIProcessor 初始化前退出，不触发 LLM 依赖。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessorThatFailsInit.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessorThatFailsInit):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "invalid-date"],
                )

    assert result.exit_code == 0
    assert "日期格式错误" in result.output
    # AIProcessor 不应被初始化
    assert len(_FakeProcessorThatFailsInit.instances) == 0


def test_existing_summary_exits_before_ai_processor_init():
    """已有总结（无 --force）应在 AIProcessor 初始化前退出。"""
    runner = CliRunner()

    class _ExistingSummaryAnalyzer(_FakeAnalyzer):
        async def get_existing_summary(self, trade_date):
            return object()  # 模拟已有总结

    _ExistingSummaryAnalyzer.instances = []
    _FakeProcessorThatFailsInit.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _ExistingSummaryAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessorThatFailsInit):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27"],
                )

    assert result.exit_code == 0
    assert "已有总结" in result.output
    # AIProcessor 不应被初始化
    assert len(_FakeProcessorThatFailsInit.instances) == 0


# ---------------------------------------------------------------------------
# Task 2.2: 新闻阶段三态展示
# ---------------------------------------------------------------------------


class _DegradedNewsAnalyzer(_FakeAnalyzer):
    """部分新闻源失败的 analyzer。"""

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "degraded",
            "telegraphs": [],
            "watch_items": [{"title": "Watch Item"}],
            "articles": [{"title": "Article"}],
            "sources_status": {
                "telegraphs": "error",
                "watch_items": "ok",
                "articles": "ok",
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


class _FailedNewsAnalyzer(_FakeAnalyzer):
    """所有新闻源失败的 analyzer。"""

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "failed",
            "telegraphs": [],
            "watch_items": [],
            "articles": [],
            "sources_status": {
                "telegraphs": "error",
                "watch_items": "error",
                "articles": "error",
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


class _PreflightSummaryAnalyzer(_FakeAnalyzer):
    """返回混合成功/失败/无数据状态，用于验证生成前预检输出。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {
                "sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045},
                "sz": {"name": "深证成指", "close": 9876.54, "change": -0.0032},
            },
            "volume": {},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
        }

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "degraded",
            "telegraphs": [],
            "watch_items": [{"title": "Watch Item"}],
            "articles": [{"title": "Article"}],
            "sources_status": {
                "telegraphs": "error",
                "watch_items": "ok",
                "articles": "ok",
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


class _AutoFetchedNewsAnalyzer(_FakeAnalyzer):
    """返回包含自动补抓摘要的新闻结果。"""

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "success",
            "telegraphs": [{"title": "Telegraph 1"}, {"title": "Telegraph 2"}],
            "watch_items": [],
            "articles": [{"title": "Article"}],
            "sources_status": {
                "telegraphs": "ok",
                "watch_items": "empty",
                "articles": "ok",
            },
            "source_details": {
                "telegraphs": {"mode": "auto_fetch_ok", "message": "已获取 2 条（自动补抓）"},
                "watch_items": {"mode": "auto_fetch_empty", "message": "0 条（已自动抓取）"},
                "articles": {"mode": "local", "message": "已获取 1 篇"},
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


class _AutoFetchFailedNewsAnalyzer(_FakeAnalyzer):
    """返回自动补抓失败的新闻结果。"""

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "degraded",
            "telegraphs": [],
            "watch_items": [],
            "articles": [{"title": "Article"}],
            "sources_status": {
                "telegraphs": "error",
                "watch_items": "error",
                "articles": "ok",
            },
            "source_details": {
                "telegraphs": {"mode": "auto_fetch_error", "message": "自动补抓失败"},
                "watch_items": {"mode": "auto_fetch_error", "message": "自动补抓失败"},
                "articles": {"mode": "local", "message": "已获取 1 篇"},
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


class _ArticleEvidenceDiagnosticsAnalyzer(_FakeAnalyzer):
    """返回文章证据诊断结果，覆盖诊断渲染路径。"""

    async def collect_news_data(self, trade_date, offline=False, **kwargs):
        self.collect_news_data_calls.append({"trade_date": trade_date, "offline": offline})
        return {
            "status": "success",
            "telegraphs": [],
            "watch_items": [],
            "articles": [{"title": "Article"}],
            "sources_status": {
                "telegraphs": "empty",
                "watch_items": "empty",
                "articles": "ok",
            },
            "article_evidence_diagnostics": {
                "total": 1,
                "prepared": 1,
                "reused": 0,
                "fallback": 0,
                "failed": 0,
            },
            "time_windows": {
                "watch": {"start": "2026-03-27 09:00", "end": "2026-03-27 15:00"},
                "telegraph": {"start": "2026-03-27 09:00", "end": "2026-03-30 09:15"},
                "article": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
            },
            "time_window": {"start": "2026-03-27 15:00", "end": "2026-03-30 09:15"},
        }


def test_news_degraded_status_shows_warning():
    """部分新闻源失败时，CLI 应展示退化提示。"""
    runner = CliRunner()
    _DegradedNewsAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _DegradedNewsAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "部分来源失败" in output
    assert "财联社电报: 获取失败" in output
    assert "看盘数据: 已获取 1 条" in output
    assert "相关文章: 已获取 1 篇" in output
    # 仍应继续生成阶段 3
    assert "生成并保存完成" in output


def test_news_failed_status_shows_error():
    """所有新闻源失败时，CLI 应展示失败提示。"""
    runner = CliRunner()
    _FailedNewsAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FailedNewsAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "所有新闻来源获取失败" in output
    assert "财联社电报: 获取失败" in output
    assert "看盘数据: 获取失败" in output
    assert "相关文章: 获取失败" in output


def test_news_success_status_shows_normal_conclusion():
    """所有新闻源成功时，CLI 应展示正常完成。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "新闻数据获取完成" in output
    # 成功时不应有退化提示
    assert "部分来源失败" not in output


def test_pre_generation_summary_shows_current_fetch_results():
    """进入生成前，CLI 应输出逐项 AI 输入数据清单。"""
    runner = CliRunner()
    _PreflightSummaryAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _PreflightSummaryAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "[预检] AI 输入数据清单" in output

    # 逐项验证：市场数据
    assert "指数: 已获取 2 个指数" in output
    assert "成交额: 获取失败" in output
    assert "涨跌统计: 已获取 2500/1800/200" in output
    assert "板块: 暂无板块数据" in output
    assert "涨停股: 0 只" in output
    # 逐项验证：新闻数据
    assert "财联社电报: 获取失败" in output
    assert "看盘数据: 已获取 1 条" in output
    assert "相关文章: 已获取 1 篇" in output

    idx_stage2 = output.find("[2/3] 获取新闻数据")
    idx_preflight = output.find("[预检] AI 输入数据清单")
    idx_stage3 = output.find("[3/3] 生成并保存市场总结")
    assert idx_stage2 < idx_preflight < idx_stage3, "生成前预检应位于阶段 2 和阶段 3 之间"


def test_input_manifest_stable_ordering():
    """输入数据清单应按固定顺序展示：市场数据 → 新闻数据。"""
    runner = CliRunner()
    _PreflightSummaryAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _PreflightSummaryAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0

    # 市场数据项应在新闻数据项之前
    idx_indices = output.find("指数: 已获取 2 个指数")
    idx_volume = output.find("成交额: 获取失败")
    idx_stats = output.find("涨跌统计: 已获取")
    idx_sectors = output.find("板块: 暂无板块数据")
    idx_limitup = output.find("涨停股: 0 只")
    idx_telegraph = output.find("财联社电报: 获取失败")
    idx_watch = output.find("看盘数据: 已获取 1 条")
    idx_article = output.find("相关文章: 已获取 1 篇")

    # 市场数据内部顺序
    assert idx_indices < idx_volume < idx_stats < idx_sectors < idx_limitup
    # 新闻数据内部顺序
    assert idx_telegraph < idx_watch < idx_article
    # 市场数据整体在新闻数据之前
    assert idx_limitup < idx_telegraph


def test_input_manifest_all_empty_sources():
    """所有来源数据为空时，输入清单仍逐项展示各状态。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "[预检] AI 输入数据清单" in output
    # 市场数据：空数据表现为 error 或 empty 状态
    assert "指数:" in output
    assert "成交额:" in output
    assert "涨跌统计:" in output
    assert "板块:" in output
    assert "涨停股:" in output
    # 新闻数据：空数据表现为 empty 状态
    assert "财联社电报: 0 条" in output
    assert "看盘数据: 0 条" in output
    assert "相关文章: 0 篇" in output


def test_news_stage_shows_auto_fetch_summary_messages():
    """阶段 2 和预检应展示自动补抓后的摘要文案。"""
    runner = CliRunner()
    _AutoFetchedNewsAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _AutoFetchedNewsAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "财联社电报: 已获取 2 条（自动补抓）" in output
    assert "看盘数据: 0 条（已自动抓取）" in output
    assert "相关文章: 已获取 1 篇" in output


def test_news_stage_shows_auto_fetch_failure_message():
    """自动补抓失败时应展示专门的失败摘要，而不是普通 0 条。"""
    runner = CliRunner()
    _AutoFetchFailedNewsAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _AutoFetchFailedNewsAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "财联社电报: 自动补抓失败" in output
    assert "看盘数据: 自动补抓失败" in output


def test_article_evidence_diagnostics_render_without_type_error():
    """文章证据诊断存在时，CLI 应正常渲染并继续生成。"""
    runner = CliRunner()
    _ArticleEvidenceDiagnosticsAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _ArticleEvidenceDiagnosticsAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "[预检] 文章证据准备" in output
    assert "文章证据: 1 篇候选（新提取 1）" in output
    assert "生成并保存完成" in output


# ---------------------------------------------------------------------------
# Task 3.2: 持久化失败回归测试
# ---------------------------------------------------------------------------


class _SaveFailureAnalyzer(_FakeAnalyzer):
    """save_summary 抛出 RuntimeError 的 analyzer。"""

    async def save_summary(self, trade_date, content, market_data, **kwargs):
        raise RuntimeError("磁盘空间不足，无法写入文件")


def test_persistence_failure_shows_error_instead_of_success():
    """save_summary 失败时，CLI 应展示保存失败而非报告成功。"""
    runner = CliRunner()
    _SaveFailureAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _SaveFailureAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "保存失败" in output
    # 不应报告完成
    assert "生成并保存完成" not in output


# ---------------------------------------------------------------------------
# Task 4.2: 宽度数据质量状态展示
# ---------------------------------------------------------------------------


class _BreadthOkAnalyzer(_FakeAnalyzer):
    """宽度数据状态为 ok 的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "eastmoney_curl", "actual_count": 5518, "expected_count": 5518},
                "statistics": {"status": "ok", "source": "eastmoney_curl", "actual_count": 5518, "expected_count": 5518},
            },
        }


class _BreadthErrorAnalyzer(_FakeAnalyzer):
    """宽度数据状态为 error 的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
            "statistics": {"up_count": 0, "down_count": 0, "flat_count": 0},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "error", "source": "eastmoney_curl", "actual_count": 0, "expected_count": 5518},
                "statistics": {"status": "error", "source": "eastmoney_curl", "actual_count": 0, "expected_count": 5518},
            },
        }


class _BreadthPartialAnalyzer(_FakeAnalyzer):
    """宽度数据状态为 partial 的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 100, "sz_volume": 200, "total_volume": 300},
            "statistics": {"up_count": 50, "down_count": 30, "flat_count": 20},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "partial", "source": "eastmoney_curl", "actual_count": 100, "expected_count": 5518},
                "statistics": {"status": "partial", "source": "eastmoney_curl", "actual_count": 100, "expected_count": 5518},
            },
        }


def test_breadth_ok_shows_success_wording():
    """宽度数据 ok 时，成交额和涨跌统计应显示"已获取"。"""
    runner = CliRunner()
    _BreadthOkAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthOkAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert "成交额: 已获取" in output
    assert "涨跌统计: 已获取" in output


def test_breadth_error_shows_failure_wording():
    """宽度数据 error 时，成交额和涨跌统计应显示"获取失败"，不应显示"已获取"。"""
    runner = CliRunner()
    _BreadthErrorAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthErrorAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    # 不应显示成功措辞
    assert "成交额: 已获取" not in output
    assert "涨跌统计: 已获取" not in output
    # 应显示失败措辞
    assert "成交额: 获取失败" in output
    assert "涨跌统计: 获取失败" in output
    assert "宽度来源: 降级为空值" in output


def test_breadth_partial_shows_sample_incomplete():
    """宽度数据 partial 时，应显示"样本不完整"提示。"""
    runner = CliRunner()
    _BreadthPartialAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthPartialAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    # 不应显示成功措辞
    assert "成交额: 已获取" not in output
    assert "涨跌统计: 已获取" not in output
    # 应显示样本不完整提示
    assert "样本不完整" in output


# ---------------------------------------------------------------------------
# Task 3.2: CLI 输出干净性 — 无第三方原始进度条或控制字符
# ---------------------------------------------------------------------------


class _TqdmLeakingAnalyzer(_FakeAnalyzer):
    """模拟宽度数据降级路径（快照失败 → 共享备用源），用于验证 CLI 输出干净。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        self.collect_market_data_calls.append(
            {"offline": offline, "trade_date": trade_date, "force": force}
        )
        return {
            "indices": {
                "sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045},
            },
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "akshare_spot_em", "actual_count": 5518, "expected_count": 5518},
                "statistics": {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
            },
        }


def test_cli_output_no_tqdm_control_characters():
    """CLI 输出不应包含 tqdm 原始控制字符（如 \\r, |, # 等进度条特征）。"""
    runner = CliRunner()
    _TqdmLeakingAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _TqdmLeakingAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0

    # 不应包含 tqdm 常见控制字符
    assert "\r" not in output
    assert "|" not in output or "板块" in output  # | 可能出现在 markdown 表格中
    assert "%" not in output or "涨跌幅" in output or "执行模式" in output  # % 可能出现在正常文案中

    # 不应包含 ANSI 进度条特征
    progress_bar_chars = ["█", "▓", "▒", "░"]
    for char in progress_bar_chars:
        assert char not in output


def test_ai_stage_starts_after_data_collection():
    """AI 生成阶段应严格在数据采集完成后开始。"""
    runner = CliRunner()
    _FakeAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _FakeAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0

    # 预检清单应在 AI 阶段之前
    idx_preflight = output.find("[预检] AI 输入数据清单")
    idx_stage3 = output.find("[3/3] 生成并保存市场总结")

    assert idx_preflight > 0, "缺少预检清单"
    assert idx_stage3 > 0, "缺少阶段 3 标题"
    assert idx_preflight < idx_stage3, "预检清单应在 AI 阶段之前"


# ---------------------------------------------------------------------------
# Task 4.3: near-complete 与涨停股来源标记展示
# ---------------------------------------------------------------------------


class _BreadthNearCompleteAnalyzer(_FakeAnalyzer):
    """涨跌统计为 near-complete 的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 5200, "down_count": 0, "flat_count": 1},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
                "statistics": {"status": "near-complete", "source": "pytdx_quotes", "actual_count": 5200, "expected_count": 5201},
            },
        }


class _LimitUpApproximateAnalyzer(_FakeAnalyzer):
    """涨停股为近似候选集的 analyzer。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [{"name": "A", "code": "001", "change": 0.1}, {"name": "B", "code": "002", "change": 0.099}],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "breadth_quality": {
                "volume": {"status": "ok", "source": "official_exchange_turnover", "actual_count": 2, "expected_count": 2},
                "statistics": {"status": "ok", "source": "pytdx_quotes", "actual_count": 5518, "expected_count": 5518},
            },
            "limit_up_quality": {"source_type": "approximate_candidates", "status": "ok"},
        }


def test_near_complete_statistics_shows_near_complete_wording():
    """near-complete 涨跌统计应显示"近完整"提示而非"已获取"或"样本不完整"。"""
    runner = CliRunner()
    _BreadthNearCompleteAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _BreadthNearCompleteAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "近完整" in output
    assert "5200/5201" in output


def test_approximate_limit_up_shows_candidate_label():
    """近似候选集涨停股应显示"近似候选"标签。"""
    runner = CliRunner()
    _LimitUpApproximateAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _LimitUpApproximateAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "近似候选" in output
    assert "2 只" in output


# ---------------------------------------------------------------------------
# Task 4.3: 海外市场 fallback 展示
# ---------------------------------------------------------------------------


class _GlobalContextFallbackAnalyzer(_FakeAnalyzer):
    """主源失败后 fallback 成功的海外市场上下文。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "global_market_context": {
                "status": "ok",
                "target_a_trade_date": "2026-03-27",
                "captured_at": "2026-03-27T22:30:00+08:00",
                "as_of": "2026-03-27T22:29:00+08:00",
                "session": "regular",
                "source": "yahoo_chart",
                "degraded": True,
                "source_attempts": [
                    {"source": "yahoo_quote", "status": "error", "failure_type": "unauthorized", "message": "401"},
                    {"source": "yahoo_chart", "status": "ok", "failure_type": "none", "message": ""},
                ],
                "us_market": {
                    "status": "ok",
                    "session": "regular",
                    "as_of": "2026-03-27T22:29:00+08:00",
                    "indices": [
                        {"symbol": "DJIA", "name": "道琼斯", "price": 39000.0, "change_pct": 0.004},
                    ],
                    "risk_signals": {},
                    "leaders": [],
                    "source": "yahoo_chart",
                },
            },
        }


class _GlobalContextAllFailAnalyzer(_FakeAnalyzer):
    """所有 provider 失败的海外市场上下文（主源 unauthorized）。"""

    async def collect_market_data(self, offline=False, trade_date=None, force=False):
        return {
            "indices": {"sh": {"name": "上证指数", "close": 3089.26, "change": 0.0045}},
            "volume": {"sh_volume": 5000.0, "sz_volume": 7000.0, "total_volume": 12000.0},
            "statistics": {"up_count": 2500, "down_count": 1800, "flat_count": 200},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
            "fetch_time": "2026-03-27T10:00:00",
            "data_source": "api",
            "global_market_context": {
                "status": "error",
                "target_a_trade_date": "2026-03-27",
                "message": "所有海外市场数据源不可用",
                "source": "yahoo_quote",
                "degraded": False,
                "source_attempts": [
                    {"source": "yahoo_quote", "status": "error", "failure_type": "unauthorized", "message": "401"},
                ],
            },
        }


def test_fallback_success_shows_fallback_label():
    """fallback 成功时，CLI 应展示 (fallback) 标签。"""
    runner = CliRunner()
    _GlobalContextFallbackAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _GlobalContextFallbackAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "(fallback)" in output


def test_all_providers_fail_shows_unauthorized_hint():
    """所有 provider 失败且主源为 401 时，CLI 应展示上游拒绝访问提示。"""
    runner = CliRunner()
    _GlobalContextAllFailAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _GlobalContextAllFailAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    output = result.output
    assert result.exit_code == 0
    assert "上游拒绝访问" in output


def test_fallback_provenance_passed_to_processor():
    """fallback 的 provenance 元数据应原样传给 AIProcessor。"""
    runner = CliRunner()
    _GlobalContextFallbackAnalyzer.instances = []
    _FakeProcessor.instances = []

    with patch("src.cli.ai.get_db", new=_fake_get_db):
        with patch("src.cli.ai.MarketAnalyzer", _GlobalContextFallbackAnalyzer):
            with patch("src.cli.ai.AIProcessor", _FakeProcessor):
                result = runner.invoke(
                    main,
                    ["ai", "market-summary", "--date", "2026-03-27", "--force"],
                )

    assert result.exit_code == 0
    call = _FakeProcessor.instances[0].generate_calls[0]
    ctx = call["global_market_context"]
    assert ctx["degraded"] is True
    assert ctx["source"] == "yahoo_chart"
    assert len(ctx["source_attempts"]) == 2
    assert ctx["source_attempts"][0]["failure_type"] == "unauthorized"
