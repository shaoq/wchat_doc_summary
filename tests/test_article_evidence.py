"""文章证据提取与缓存服务测试 — 验证 schema、提取、缓存、批量准备、降级等场景。"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.schema import Article, ArticleProcessing, Feed
from src.services.article_evidence import (
    ArticleEvidenceService,
    ArticleRelevance,
    BatchPreparationResult,
    EvidenceOutcome,
    MarketArticleEvidence,
    compute_relevance_score,
    parse_evidence_json,
    validate_evidence_dict,
    TASK_TYPE,
)


# ---------------------------------------------------------------------------
# Schema 验证测试 (Task 5.1)
# ---------------------------------------------------------------------------


class TestEvidenceSchema:
    """测试 MarketArticleEvidence schema 的验证逻辑。"""

    def test_valid_evidence_dict(self) -> None:
        """正常证据字典应通过验证。"""
        data = {
            "article_type": "review",
            "relevance": "high",
            "time_role": "post_close_review",
            "mentioned_sectors": ["半导体", "人工智能"],
            "mentioned_stocks": ["中芯国际(688981)"],
            "mainline_views": ["半导体为今日主线"],
            "sentiment_view": "bullish",
            "next_day_watch_items": ["关注半导体持续性"],
            "risk_points": ["成交量萎缩"],
            "usable_summary": "市场情绪偏暖，半导体领涨",
        }
        evidence = validate_evidence_dict(data)
        assert evidence is not None
        assert evidence.article_type == "review"
        assert evidence.relevance == "high"
        assert evidence.mentioned_sectors == ("半导体", "人工智能")

    def test_missing_required_field_returns_none(self) -> None:
        """缺少必填字段应返回 None。"""
        data = {"article_type": "review"}  # 缺少 relevance 和 usable_summary
        assert validate_evidence_dict(data) is None

    def test_none_input_returns_none(self) -> None:
        """None 输入应返回 None。"""
        assert validate_evidence_dict(None) is None

    def test_empty_dict_returns_none(self) -> None:
        """空字典应返回 None。"""
        assert validate_evidence_dict({}) is None

    def test_defaults_filled_for_missing_optional_fields(self) -> None:
        """缺失的可选字段应用默认值填充。"""
        data = {"relevance": "low", "article_type": "news", "usable_summary": "test"}
        evidence = validate_evidence_dict(data)
        assert evidence is not None
        assert evidence.mentioned_sectors == ()
        assert evidence.sentiment_view == ""

    def test_invalid_relevance_gets_default(self) -> None:
        """无效的 relevance 值应回退到 low。"""
        data = {
            "relevance": "super_high",
            "article_type": "review",
            "usable_summary": "test",
        }
        evidence = validate_evidence_dict(data)
        assert evidence is not None
        assert evidence.relevance == "low"

    def test_non_list_sectors_normalized(self) -> None:
        """非列表类型的板块字段应被规范化为空列表。"""
        data = {
            "relevance": "low",
            "article_type": "review",
            "usable_summary": "test",
            "mentioned_sectors": "not-a-list",
        }
        evidence = validate_evidence_dict(data)
        assert evidence is not None
        assert evidence.mentioned_sectors == ()

    def test_to_dict_round_trip(self) -> None:
        """to_dict → validate_evidence_dict 往返应保持数据一致。"""
        original = MarketArticleEvidence(
            article_type="strategy",
            relevance="medium",
            mentioned_sectors=("消费",),
            usable_summary="明日关注消费复苏",
        )
        data = original.to_dict()
        restored = validate_evidence_dict(data)
        assert restored is not None
        assert restored.article_type == original.article_type
        assert restored.relevance == original.relevance
        assert restored.mentioned_sectors == original.mentioned_sectors


class TestParseEvidenceJson:
    """测试 JSON 解析逻辑。"""

    def test_valid_json(self) -> None:
        """有效 JSON 应解析成功。"""
        raw = json.dumps({
            "relevance": "high",
            "article_type": "review",
            "usable_summary": "test",
        })
        evidence = parse_evidence_json(raw)
        assert evidence is not None
        assert evidence.relevance == "high"

    def test_malformed_json_returns_none(self) -> None:
        """畸形 JSON 应返回 None。"""
        assert parse_evidence_json("{invalid") is None

    def test_empty_string_returns_none(self) -> None:
        """空字符串应返回 None。"""
        assert parse_evidence_json("") is None
        assert parse_evidence_json(None) is None


# ---------------------------------------------------------------------------
# 相关度评分测试 (Task 5.2)
# ---------------------------------------------------------------------------


class TestRelevanceScoring:
    """测试确定性文章相关度评分。"""

    def test_review_keywords_high_score(self) -> None:
        """复盘类关键词应获得高分。"""
        score = compute_relevance_score("A股收评：市场大涨", "", True)
        assert score >= 30

    def test_strategy_keywords_score(self) -> None:
        """策略类关键词应获得较高分。"""
        score = compute_relevance_score("明日操作策略", "", False)
        assert score >= 25

    def test_no_keywords_low_score(self) -> None:
        """无关键词的文章应得低分。"""
        score = compute_relevance_score("美食探店之旅", "今天吃了好吃的", True)
        assert score < 20

    def test_multiple_keywords_add_up(self) -> None:
        """多个关键词信号应叠加。"""
        score = compute_relevance_score(
            "复盘：主线半导体，策略关注AI板块，风险提示", "", True,
        )
        assert score >= 50

    def test_content_available_bonus(self) -> None:
        """有正文内容应有加成。"""
        with_content = compute_relevance_score("标题", "", True)
        without = compute_relevance_score("标题", "", False)
        assert with_content > without

    def test_score_capped_at_100(self) -> None:
        """分数应上限为 100。"""
        score = compute_relevance_score(
            "复盘策略主线板块情绪涨停关注风险" * 10, "摘要" * 100, True,
        )
        assert score <= 100


# ---------------------------------------------------------------------------
# 缓存查询测试 (Task 5.1)
# ---------------------------------------------------------------------------


class TestCachedEvidenceLookup:
    """测试缓存证据查询和畸形 JSON 处理。"""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db: MagicMock) -> ArticleEvidenceService:
        return ArticleEvidenceService(mock_db)

    @pytest.mark.asyncio
    async def test_cached_valid_evidence_returned(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """有效缓存证据应被返回。"""
        processing = ArticleProcessing(
            id=1, article_id=10, task_type=TASK_TYPE, status="success",
            result=json.dumps({
                "relevance": "high", "article_type": "review", "usable_summary": "test",
            }),
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = processing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        evidence = await service.get_cached_evidence(10)
        assert evidence is not None
        assert evidence.relevance == "high"

    @pytest.mark.asyncio
    async def test_malformed_cached_json_returns_none(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """畸形缓存 JSON 应返回 None（不静默信任）。"""
        processing = ArticleProcessing(
            id=1, article_id=10, task_type=TASK_TYPE, status="success",
            result="{broken json!!!",
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = processing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        evidence = await service.get_cached_evidence(10)
        assert evidence is None

    @pytest.mark.asyncio
    async def test_no_cache_returns_none(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """无缓存应返回 None。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        evidence = await service.get_cached_evidence(999)
        assert evidence is None


# ---------------------------------------------------------------------------
# 提取降级测试 (Task 5.1, 5.6)
# ---------------------------------------------------------------------------


class TestExtractionDegradation:
    """测试内容不足时的降级行为。"""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db: MagicMock) -> ArticleEvidenceService:
        return ArticleEvidenceService(mock_db)

    @pytest.mark.asyncio
    async def test_title_only_fallback(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """仅有标题无内容时应降级为 fallback。"""
        article = Article(id=1, title="测试标题", summary=None, content=None)

        mock_session = AsyncMock()
        # First query: load article
        article_result = MagicMock()
        article_result.scalar_one_or_none.return_value = article
        # Second query: load feed (no feed)
        feed_result = MagicMock()
        feed_result.scalar_one_or_none.return_value = None
        # Third query: cached evidence
        cache_result = MagicMock()
        cache_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[article_result, feed_result, cache_result]
        )
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        record = await service.extract_evidence(1)
        assert record.outcome == EvidenceOutcome.FALLBACK
        assert record.evidence.usable_summary == "测试标题"

    @pytest.mark.asyncio
    async def test_empty_article_skipped(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """完全空白的文章应被跳过。"""
        article = Article(id=2, title=None, summary=None, content=None, feed_id=None)

        mock_session = AsyncMock()
        article_result = MagicMock()
        article_result.scalar_one_or_none.return_value = article
        feed_result = MagicMock()
        feed_result.scalar_one_or_none.return_value = None
        cache_result = MagicMock()
        cache_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[article_result, feed_result, cache_result]
        )
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        record = await service.extract_evidence(2)
        assert record.outcome == EvidenceOutcome.SKIPPED

    @pytest.mark.asyncio
    async def test_ai_failure_fallback(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """AI 提取失败时应降级，不应导致整体失败。"""
        article = Article(id=3, title="复盘文章", summary="今日市场总结", content=None, feed_id=None)

        mock_session = AsyncMock()
        article_result = MagicMock()
        article_result.scalar_one_or_none.return_value = article
        feed_result = MagicMock()
        feed_result.scalar_one_or_none.return_value = None
        cache_result = MagicMock()
        cache_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[article_result, feed_result, cache_result]
        )
        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch.object(service, "_call_ai_extraction", side_effect=RuntimeError("API error")):
            record = await service.extract_evidence(3)

        assert record.outcome == EvidenceOutcome.FAILED
        assert record.title == "复盘文章"


# ---------------------------------------------------------------------------
# 批量准备测试 (Task 5.1)
# ---------------------------------------------------------------------------


class TestBatchPreparation:
    """测试有界批量准备。"""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        db = MagicMock()
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db: MagicMock) -> ArticleEvidenceService:
        return ArticleEvidenceService(mock_db)

    @pytest.mark.asyncio
    async def test_batch_respects_max_candidates(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """批量准备应限制在最大候选数。"""
        articles = [
            {"id": i, "title": f"文章{i}", "summary": f"摘要{i}", "content": ""}
            for i in range(1, 21)
        ]

        # Mock extract_evidence to return fallback records
        with patch.object(service, "extract_evidence", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = MagicMock(
                outcome=EvidenceOutcome.FALLBACK,
                records=[],
            )
            result = await service.prepare_batch(articles, max_candidates=5)

        assert result.total == 20  # 总数是全部文章
        # 应只处理 5 个候选
        assert mock_extract.call_count == 5

    @pytest.mark.asyncio
    async def test_batch_scores_and_sorts(
        self, service: ArticleEvidenceService, mock_db: MagicMock,
    ) -> None:
        """批量准备应按相关度排序，高相关度优先。"""
        articles = [
            {"id": 1, "title": "普通文章", "summary": "日常内容", "content": ""},
            {"id": 2, "title": "A股收评：半导体领涨", "summary": "复盘市场行情", "content": "有内容"},
            {"id": 3, "title": "美食推荐", "summary": "今日探店", "content": ""},
        ]

        call_order: list[int] = []

        async def mock_extract(article_id: int, **kwargs: object) -> MagicMock:
            call_order.append(article_id)
            return MagicMock(outcome=EvidenceOutcome.FALLBACK)

        with patch.object(service, "extract_evidence", side_effect=mock_extract):
            await service.prepare_batch(articles, max_candidates=2)

        # 复盘文章 (id=2) 应排在第一位
        assert call_order[0] == 2


# ---------------------------------------------------------------------------
# Prompt 格式化测试 (Task 5.5)
# ---------------------------------------------------------------------------


class TestPromptFormatting:
    """测试文章证据 prompt 格式化。"""

    @pytest.fixture
    def processor(self) -> "AIProcessor":
        from src.services.ai_processor import AIProcessor
        mock_db = MagicMock()
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings") as mock_settings:
                settings = MagicMock()
                settings.llm_api_key = "test"
                settings.llm_base_url = "https://test.com"
                settings.llm_model = "test-model"
                mock_settings.return_value = settings
                return AIProcessor(mock_db)

    def test_format_evidence_renders_structured_viewpoints(
        self, processor: "AIProcessor",
    ) -> None:
        """结构化证据应渲染为包含板块、个股、主线的格式。"""
        records = [
            {
                "article_id": 1,
                "title": "收评：半导体全线爆发",
                "outcome": "prepared",
                "feed_name": "财经内参",
                "evidence": {
                    "article_type": "review",
                    "relevance": "high",
                    "mentioned_sectors": ["半导体", "芯片"],
                    "mentioned_stocks": ["中芯国际(688981)"],
                    "mainline_views": ["半导体为今日主线"],
                    "sentiment_view": "bullish",
                    "next_day_watch_items": ["关注半导体持续性"],
                    "risk_points": ["成交量萎缩"],
                    "usable_summary": "半导体全线爆发，中芯国际涨停",
                },
            },
        ]
        result = processor._format_article_evidence_for_prompt(records)

        assert "半导体" in result
        assert "中芯国际" in result
        assert "主线观点" in result
        assert "情绪倾向: bullish" in result
        assert "明日关注" in result
        assert "风险提示" in result
        assert "来源: 财经内参" in result

    def test_format_evidence_fallback_marker(
        self, processor: "AIProcessor",
    ) -> None:
        """降级证据应标记为[降级]。"""
        records = [
            {
                "article_id": 1,
                "title": "测试",
                "outcome": "fallback",
                "evidence": {
                    "relevance": "low",
                    "article_type": "unknown",
                    "usable_summary": "仅标题",
                },
            },
        ]
        result = processor._format_article_evidence_for_prompt(records)
        assert "[降级" in result

    def test_format_evidence_empty_returns_fallback(
        self, processor: "AIProcessor",
    ) -> None:
        """空证据列表应返回无相关新闻。"""
        result = processor._format_article_evidence_for_prompt([])
        assert "无相关新闻" in result

    def test_format_evidence_unrelated_filtered(
        self, processor: "AIProcessor",
    ) -> None:
        """无关文章应被过滤。"""
        records = [
            {
                "article_id": 1,
                "title": "美食推荐",
                "outcome": "prepared",
                "evidence": {
                    "relevance": "unrelated",
                    "article_type": "other",
                    "usable_summary": "美食文章",
                },
            },
        ]
        result = processor._format_article_evidence_for_prompt(records)
        assert "非市场复盘" in result

    def test_format_evidence_includes_watch_and_risk(
        self, processor: "AIProcessor",
    ) -> None:
        """格式化输出应包含明日关注和风险提示。"""
        records = [
            {
                "article_id": 1,
                "title": "策略",
                "outcome": "prepared",
                "evidence": {
                    "relevance": "high",
                    "article_type": "strategy",
                    "next_day_watch_items": ["关注AI持续性"],
                    "risk_points": ["成交量萎缩"],
                    "usable_summary": "test",
                },
            },
        ]
        result = processor._format_article_evidence_for_prompt(records)
        assert "关注AI持续性" in result
        assert "成交量萎缩" in result


# ---------------------------------------------------------------------------
# 市场总结集成测试 (Task 5.6)
# ---------------------------------------------------------------------------


class TestMarketSummaryIntegration:
    """测试市场总结中的文章证据降级和集成。"""

    def test_candidate_selection_uses_relevance(self) -> None:
        """候选选择应按相关度排序。"""
        from src.services.market_analyzer import MarketAnalyzer

        articles = [
            {"id": 1, "title": "普通文章", "summary": "日常", "content": "", "feed_weight": 5},
            {"id": 2, "title": "A股收评：半导体领涨", "summary": "复盘市场行情", "content": "详细内容", "feed_weight": 8},
            {"id": 3, "title": "明日策略布局", "summary": "关注AI", "content": "", "feed_weight": 5},
        ]

        candidates = MarketAnalyzer.select_evidence_candidates(articles, max_candidates=2)
        # 复盘+高权重文章应排第一
        assert candidates[0]["id"] == 2

    def test_fallback_signals_from_titles(self) -> None:
        """降级信号应从标题和摘要构建。"""
        from src.services.market_analyzer import MarketAnalyzer

        articles = [
            {"title": "文章1", "summary": "摘要1", "feed_name": "测试源"},
            {"title": "文章2", "summary": "摘要2"},
        ]
        fallback = MarketAnalyzer.build_fallback_article_signals(articles)

        assert len(fallback) == 2
        assert fallback[0]["fallback"] is True
        assert fallback[0]["feed_name"] == "测试源"
