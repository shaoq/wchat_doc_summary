"""AI 内容安全重试与策略增强降级测试。"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.ai_processor import AIProcessor


def _make_processor() -> AIProcessor:
    """创建一个 mock AIProcessor 实例。"""
    mock_db = MagicMock()
    mock_settings = MagicMock()
    mock_settings.llm_api_key = "test_key"
    mock_settings.llm_base_url = "https://test.api.com"
    mock_settings.llm_model = "test-model"
    mock_settings.max_retries = 2
    with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
        with patch("src.services.ai_processor.AsyncAnthropic"):
            processor = AIProcessor(mock_db)
    return processor


def _full_market_data() -> dict:
    """构造完整的市场数据。"""
    return {
        "indices": {
            "sh000001": {"name": "上证指数", "close": 3100.50, "change": 0.015},
            "sz399001": {"name": "深证成指", "close": 10200.30, "change": 0.012},
        },
        "volume": {"total_volume": "8500"},
        "statistics": {"up_count": 3200, "down_count": 1600, "flat_count": 200},
        "sectors": {
            "top_sectors": [
                {"name": "电力", "change": 0.035},
                {"name": "军工", "change": 0.028},
            ],
            "bottom_sectors": [
                {"name": "油气", "change": -0.015},
            ],
        },
        "limit_up": [
            {"name": "华电辽能", "code": "600739"},
            {"name": "长城军工", "code": "601606"},
        ],
        "global_market_context": {
            "status": "ok",
            "session": "regular",
            "as_of": "2024-03-15T22:29:00+08:00",
            "source": "yahoo_quote",
            "us_market": {
                "indices": [
                    {"symbol": "SPX", "name": "标普500", "price": 5200.0, "change_pct": 0.006},
                ],
                "risk_signals": {},
                "leaders": [],
                "source": "yahoo_quote",
            },
        },
    }


def _full_articles() -> list[dict]:
    return [{"title": "电力板块爆发分析", "summary": "电力板块全面爆发"}]


def _full_telegraphs() -> list[dict]:
    return [{"publish_time": "2024-03-15 09:30", "title": "重要政策", "content": "政策内容"}]


def _full_watch_items() -> list[dict]:
    return [
        {
            "publish_time": "2024-03-15 10:00",
            "title": "电力拉升",
            "content": "电力板块盘中拉升",
            "stocks": ["华电辽能"],
            "sectors": ["电力"],
        },
    ]


def _weak_strategy_summary() -> str:
    """返回一个第六节过弱、需要增强的总结。"""
    return """## 一、市场概览
市场整体震荡。

## 二、主线与轮动
电力和军工活跃。

## 三、个股与情绪
情绪一般。

## 四、关键信息催化
有政策消息催化。

## 五、明日观察清单
- 电力

## 六、后续策略建议与风险提示
继续关注热点和龙头表现，注意风险。"""


def _enhanced_strategy() -> str:
    """返回一个完整的增强第六节。"""
    return """## 六、后续策略建议与风险提示
### 6.1 主线与板块策略
- **观察/策略**: 看多电力主线
  - **依据**: 电力板块涨幅前列
  - **应对**: 次日竞价观察
  - **风险**: 高开低走
- **观察/策略**: 观察军工持续性
  - **依据**: 军工板块强势
  - **应对**: 等待确认
  - **风险**: 仅脉冲

### 6.2 个股与情绪策略
- **观察/策略**: 观察高标溢价
  - **依据**: 涨停集中电力
  - **应对**: 承接稳定可跟踪
  - **风险**: 高标走弱

### 6.3 关键消息与事件策略
- **观察/策略**: 观察政策发酵
  - **依据**: 电报有政策标题
  - **应对**: 有增量消息提升优先级
  - **风险**: 无新增量则按日内处理"""


class TestContentSafetyDetection:
    """测试内容安全错误识别。"""

    def test_detects_1301_error(self) -> None:
        """应识别 1301 错误码为内容安全错误。"""
        processor = _make_processor()
        error = Exception("API error: '1301' sensitive content")
        assert processor._is_content_safety_error(error) is True

    def test_detects_sensitive_keyword(self) -> None:
        """应识别'敏感内容'关键字。"""
        processor = _make_processor()
        error = Exception("检测到敏感内容")
        assert processor._is_content_safety_error(error) is True

    def test_detects_unsafe_keyword(self) -> None:
        """应识别'不安全'关键字。"""
        processor = _make_processor()
        error = Exception("内容不安全")
        assert processor._is_content_safety_error(error) is True

    def test_non_safety_error_not_detected(self) -> None:
        """非安全错误不应被识别。"""
        processor = _make_processor()
        error = Exception("Network timeout")
        assert processor._is_content_safety_error(error) is False


class TestStageAwareLogging:
    """测试 stage 参数在日志中体现。"""

    @pytest.mark.asyncio
    async def test_call_api_passes_stage_to_log_on_safety_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """内容安全审查失败时，日志应包含 stage 标识。"""
        processor = _make_processor()
        safety_error = Exception("'1301' content safety error")

        with patch.object(
            processor.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = safety_error
            with pytest.raises(Exception, match="1301"):
                await processor._call_api(
                    "test prompt", max_tokens=100, stage="strategy-enhancement"
                )

        # 验证日志包含 stage
        safety_logs = [
            r for r in caplog.records if "strategy-enhancement" in r.message
        ]
        assert len(safety_logs) > 0

    @pytest.mark.asyncio
    async def test_call_api_without_stage_still_works(self) -> None:
        """不传 stage 时，_call_api 仍正常工作。"""
        processor = _make_processor()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="result")]
        mock_response.content[0].text = "result"

        with patch.object(
            processor.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await processor._call_api("test prompt", max_tokens=100)

        assert result == "result"


class TestRepeatedSafetyFailure:
    """测试去敏后仍失败的行为。"""

    @pytest.mark.asyncio
    async def test_safety_failure_after_sanitization_raises_immediately(self) -> None:
        """去敏后仍触发安全审查时，应立即抛出异常，不再重试。"""
        processor = _make_processor()
        safety_error = Exception("'1301' content safety")

        call_count = 0

        async def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise safety_error

        with patch.object(
            processor.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = always_fail
            with pytest.raises(Exception, match="1301"):
                await processor._call_api("test prompt", max_tokens=100)

        # 第一次：原始 prompt 失败 → 去敏
        # 第二次：去敏后 prompt 失败 → 立即 raise
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_final_error_preserves_original_provider_error(self) -> None:
        """最终抛出的错误应保留原始 provider 错误信息。"""
        processor = _make_processor()
        original_error = Exception("'1301' content flagged by provider safety review")

        async def always_fail(*args, **kwargs):
            raise original_error

        with patch.object(
            processor.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = always_fail
            with pytest.raises(Exception) as exc_info:
                await processor._call_api("test prompt", max_tokens=100)

        assert "provider safety review" in str(exc_info.value)


class TestStrategyEnhancementFallback:
    """测试策略增强失败时的降级行为。"""

    @pytest.mark.asyncio
    async def test_strategy_enhancement_safety_failure_preserves_first_pass(
        self,
    ) -> None:
        """策略增强被内容安全审查拦截时，应返回首轮总结。"""
        processor = _make_processor()
        first_pass = _weak_strategy_summary()
        safety_error = Exception("'1301' sensitive")

        call_count = 0

        async def mock_call_api(
            prompt: str, max_tokens: int = 500, *, stage: str = ""
        ) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_pass
            raise safety_error

        processor._call_api = mock_call_api

        result = await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert result == first_pass
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_strategy_enhancement_generic_failure_preserves_first_pass(
        self,
    ) -> None:
        """策略增强因非安全错误失败时，也应返回首轮总结。"""
        processor = _make_processor()
        first_pass = _weak_strategy_summary()

        call_count = 0

        async def mock_call_api(
            prompt: str, max_tokens: int = 500, *, stage: str = ""
        ) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_pass
            raise RuntimeError("Network timeout")

        processor._call_api = mock_call_api

        result = await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert result == first_pass

    @pytest.mark.asyncio
    async def test_initial_summary_safety_failure_is_fatal(self) -> None:
        """初始总结的内容安全失败应直接抛出异常。"""
        processor = _make_processor()
        safety_error = Exception("'1301' sensitive")

        async def mock_call_api(
            prompt: str, max_tokens: int = 500, *, stage: str = ""
        ) -> str:
            raise safety_error

        processor._call_api = mock_call_api

        with pytest.raises(Exception, match="1301"):
            await processor.generate_market_summary(
                trade_date="2024-03-15",
                market_data=_full_market_data(),
                articles=_full_articles(),
                telegraphs=_full_telegraphs(),
                watch_items=_full_watch_items(),
            )

    @pytest.mark.asyncio
    async def test_successful_enhancement_still_merges(self) -> None:
        """策略增强成功时，仍应正常合并。"""
        processor = _make_processor()
        first_pass = _weak_strategy_summary()
        enhanced = _enhanced_strategy()

        call_count = 0

        async def mock_call_api(
            prompt: str, max_tokens: int = 500, *, stage: str = ""
        ) -> str:
            nonlocal call_count
            call_count += 1
            return first_pass if call_count == 1 else enhanced

        processor._call_api = mock_call_api

        result = await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert "### 6.1 主线与板块策略" in result
        assert "继续关注热点和龙头表现" not in result


class TestPriorContextDigest:
    """测试前五节简洁摘要生成。"""

    def test_builds_concise_digest_from_sections(self) -> None:
        """应从前五节中提取核心结论摘要。"""
        processor = _make_processor()
        summary = """## 一、市场概览
市场震荡走高，成交额放大。

## 二、主线与轮动
电力板块领涨，军工跟随。

## 三、个股与情绪
涨停集中在电力和军工。

## 四、关键信息催化
政策利好推动电力板块。

## 五、明日观察清单
- 电力板块回流强度

## 六、后续策略建议与风险提示
继续关注。"""

        digest = processor._build_prior_context_digest(summary)
        assert "市场概览" in digest
        assert "主线与轮动" in digest
        assert "个股与情绪" in digest
        assert "关键信息催化" in digest
        assert "明日观察清单" in digest

    def test_empty_summary_returns_no_content(self) -> None:
        """没有前五节内容时，应返回各节'无'标记。"""
        processor = _make_processor()
        digest = processor._build_prior_context_digest("## 六、后续策略建议与风险提示\n一些策略")
        assert "无前五节内容" in digest


class TestFilterSafeTitles:
    """测试标题敏感词过滤。"""

    def test_filters_sensitive_titles(self) -> None:
        """应过滤包含敏感词的标题。"""
        processor = _make_processor()
        titles = [
            "电力板块大涨",
            "习近平发表重要讲话",
            "军工行业分析",
            "法轮功相关报道",
        ]
        safe = processor._filter_safe_titles(titles)
        assert "电力板块大涨" in safe
        assert "军工行业分析" in safe
        assert len(safe) == 2

    def test_all_safe_titles_pass(self) -> None:
        """所有安全标题应原样通过。"""
        processor = _make_processor()
        titles = ["电力板块大涨", "军工行业分析", "新能源政策解读"]
        safe = processor._filter_safe_titles(titles)
        assert safe == titles

    def test_all_sensitive_returns_empty(self) -> None:
        """全部敏感时返回空列表。"""
        processor = _make_processor()
        titles = ["习近平讲话", "法轮功报道"]
        safe = processor._filter_safe_titles(titles)
        assert safe == []

    def test_empty_strings_are_skipped(self) -> None:
        """空字符串标题应被跳过。"""
        processor = _make_processor()
        titles = ["", "电力板块", ""]
        safe = processor._filter_safe_titles(titles)
        assert safe == ["电力板块"]


class TestSanitizationPreservesStructuredFacts:
    """测试去敏处理保留结构化市场数据。"""

    def test_preserves_index_values(self) -> None:
        """去敏应保留指数数值。"""
        processor = _make_processor()
        prompt = """市场数据：
- 上证指数: 3100.50 (+1.50%)
- 深证成指: 10200.30 (+1.20%)
"""
        result = processor._sanitize_prompt(prompt)
        assert "3100.50" in result
        assert "10200.30" in result
        assert "上证指数" in result

    def test_preserves_volume_and_breadth(self) -> None:
        """去敏应保留成交额和涨跌家数。"""
        processor = _make_processor()
        prompt = """成交额: 8500 亿元
上涨 3200 家，下跌 1600 家，平盘 200 家
"""
        result = processor._sanitize_prompt(prompt)
        assert "8500" in result
        assert "3200" in result
        assert "1600" in result

    def test_preserves_sector_names_and_changes(self) -> None:
        """去敏应保留板块名称和涨跌幅。"""
        processor = _make_processor()
        prompt = """强势板块: 电力(+3.50%), 军工(+2.80%)
弱势板块: 油气(-1.50%)
"""
        result = processor._sanitize_prompt(prompt)
        assert "电力" in result
        assert "军工" in result
        assert "+3.50%" in result
        assert "油气" in result

    def test_preserves_stock_names_and_codes(self) -> None:
        """去敏应保留个股名称和代码。"""
        processor = _make_processor()
        prompt = """涨停股: 华电辽能(600739), 长城军工(601606)
"""
        result = processor._sanitize_prompt(prompt)
        assert "华电辽能" in result
        assert "600739" in result
        assert "长城军工" in result

    def test_removes_sensitive_news_items(self) -> None:
        """去敏应移除命中敏感词的新闻条目。"""
        processor = _make_processor()
        prompt = """1. 电力板块爆发分析
   摘要：电力板块全面爆发...
2. 习近平发表重要讲话
   摘要：关于经济政策...
3. 军工行业前景分析
"""
        result = processor._sanitize_prompt(prompt)
        assert "电力板块爆发分析" in result
        assert "军工行业前景分析" in result
        assert "习近平" not in result
        assert "关于经济政策" not in result

    def test_preserves_global_market_context(self) -> None:
        """去敏应保留海外市场上下文。"""
        processor = _make_processor()
        prompt = """海外市场上下文：
美股指数：
- 道琼斯工业平均指数: 39000.0 (+0.40%)
- 标普500: 5200.0 (+0.60%)
风险信号：VIX 13.5
"""
        result = processor._sanitize_prompt(prompt)
        assert "道琼斯" in result
        assert "39000.0" in result
        assert "标普500" in result
        assert "VIX" in result

    def test_preserves_data_gaps(self) -> None:
        """去敏应保留数据缺口信息。"""
        processor = _make_processor()
        prompt = """⚠️ 以下证据组数据不足：
- 海外市场上下文缺失
- 涨停个股数据缺失
"""
        result = processor._sanitize_prompt(prompt)
        assert "海外市场上下文缺失" in result
        assert "涨停个股数据缺失" in result


class TestEvidenceDigestFiltersSensitiveTitles:
    """测试策略证据摘要中的标题过滤。"""

    def test_evidence_digest_filters_sensitive_telegraph_titles(self) -> None:
        """策略证据摘要应过滤敏感电报标题。"""
        processor = _make_processor()
        digest = processor._build_strategy_evidence_digest(
            indices_summary="上证 3100 (+1.5%)",
            volume="8500",
            stats={"up_count": 3200, "down_count": 1600, "flat_count": 200},
            top_sectors=[{"name": "电力", "change": 0.035}],
            bottom_sectors=[{"name": "油气", "change": -0.015}],
            limit_up=[{"name": "华电辽能", "code": "600739"}],
            telegraphs=[
                {"title": "重要政策", "content": "政策内容"},
                {"title": "习近平讲话", "content": "内容"},
            ],
            watch_items=[],
            articles=[],
            global_market_context=None,
            data_gaps="无",
        )

        assert "重要政策" in digest
        assert "习近平" not in digest

    def test_evidence_digest_marks_all_filtered_as_unavailable(self) -> None:
        """所有标题被过滤时，应标记为不可用。"""
        processor = _make_processor()
        digest = processor._build_strategy_evidence_digest(
            indices_summary="上证 3100",
            volume="8500",
            stats={"up_count": 100, "down_count": 50, "flat_count": 10},
            top_sectors=[],
            bottom_sectors=[],
            limit_up=[],
            telegraphs=[
                {"title": "习近平讲话", "content": ""},
                {"title": "法轮功报道", "content": ""},
            ],
            watch_items=[],
            articles=[
                {"title": "六四相关", "summary": ""},
            ],
            global_market_context=None,
            data_gaps="无",
        )

        assert "事件标题证据不可用" in digest
        assert "文章标题证据不可用" in digest

    def test_evidence_digest_preserves_structured_facts(self) -> None:
        """策略证据摘要应保留结构化市场数据。"""
        processor = _make_processor()
        digest = processor._build_strategy_evidence_digest(
            indices_summary="上证 3100 (+1.5%)",
            volume="8500",
            stats={"up_count": 3200, "down_count": 1600, "flat_count": 200},
            top_sectors=[{"name": "电力", "change": 0.035}],
            bottom_sectors=[{"name": "油气", "change": -0.015}],
            limit_up=[{"name": "华电辽能", "code": "600739"}],
            telegraphs=[],
            watch_items=[
                {
                    "title": "电力拉升",
                    "stocks": ["华电辽能"],
                    "sectors": ["电力"],
                },
            ],
            articles=[],
            global_market_context={"status": "ok", "session": "regular", "as_of": "2024-03-15", "source": "test", "us_market": {"indices": [], "risk_signals": {}, "leaders": []}},
            data_gaps="无",
        )

        assert "上证 3100" in digest
        assert "8500" in digest
        assert "3200" in digest
        assert "电力" in digest
        assert "华电辽能" in digest
