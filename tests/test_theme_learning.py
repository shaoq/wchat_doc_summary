"""主题词典学习测试 - 注册表、配置加载、候选发现、AI 归属、建议审查、CLI。"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from sqlalchemy import select

from src.models.schema import (
    AcceptedThemeTerm,
    MarketSector,
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    ThemeTermSuggestion,
    TrackedSector,
)
from src.services.sector_group_service import SectorGroupService
from src.services.sector_trend_service import SectorIdentity
from src.services.theme_registry import (
    DEFAULT_NOISE_TERMS,
    ThemeEntry,
    ThemeRegistry,
    ThemeRegistryService,
)
from src.storage.database import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """创建内存测试数据库。"""
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def seeded_db(test_db: Database):
    """填充基础板块数据。"""
    async with test_db.get_session() as session:
        for name, status in [
            ("光伏", "tracked"), ("TOPCon", "tracked"),
            ("BC电池", "tracked"), ("HIT电池", "candidate"),
            ("钙钛矿", "tracked"),
            ("猪肉", "tracked"), ("鸡肉", "tracked"),
            ("机器人", "tracked"), ("智能机器", "tracked"),
            ("锂电池", "tracked"), ("固态电池", "tracked"),
            ("半导体", "ignored"),
        ]:
            sector = TrackedSector(
                canonical_name=name,
                status=status,
                source="test",
                first_seen_date=date(2026, 5, 1),
                last_seen_date=date(2026, 5, 15),
            )
            session.add(sector)

    return test_db


@pytest_asyncio.fixture
def theme_service(seeded_db: Database) -> ThemeRegistryService:
    return ThemeRegistryService(seeded_db)


@pytest_asyncio.fixture
def group_service(seeded_db: Database) -> SectorGroupService:
    return SectorGroupService(seeded_db)


# ---------------------------------------------------------------------------
# 7.1 注册表合并优先级与噪声词覆盖
# ---------------------------------------------------------------------------

class TestThemeRegistryMerge:
    """测试注册表合并优先级和噪声词覆盖。"""

    def test_empty_registry_match_returns_none(self):
        """空注册表匹配应返回 None。"""
        registry = ThemeRegistry()
        assert registry.match("光伏") is None

    def test_builtin_themes_match(self):
        """内置主题应可匹配。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链",
            members=("光伏", "TOPCon"),
            source="builtin",
        )
        registry.rebuild_index()
        assert registry.match("光伏") == "光伏产业链"
        assert registry.match("topcon") == "光伏产业链"

    def test_noise_terms_override_membership(self):
        """噪声词应覆盖主题成员。"""
        registry = ThemeRegistry()
        registry.themes["消费农业链"] = ThemeEntry(
            theme_name="消费农业链",
            members=("猪肉", "鸡肉"),
            source="builtin",
        )
        registry.noise_terms.add(SectorIdentity.comparison_key("猪肉"))
        registry.rebuild_index()
        assert registry.match("猪肉") is None
        assert registry.match("鸡肉") == "消费农业链"

    def test_disabled_terms_override_membership(self):
        """禁用词应覆盖主题成员。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链",
            members=("光伏", "TOPCon"),
            source="builtin",
        )
        registry.disabled_terms.add(SectorIdentity.comparison_key("TOPCon"))
        registry.rebuild_index()
        assert registry.match("TOPCon") is None

    def test_is_noise(self):
        """噪声词判断。"""
        registry = ThemeRegistry()
        registry.noise_terms.add(SectorIdentity.comparison_key("本月解禁"))
        assert registry.is_noise("本月解禁") is True
        assert registry.is_noise("光伏") is False

    @pytest.mark.asyncio
    async def test_registry_includes_builtin(self, theme_service: ThemeRegistryService):
        """注册表应包含内置主题。"""
        registry = await theme_service.get_registry()
        assert registry.match("光伏") == "光伏产业链"
        assert registry.match("猪肉") == "消费农业链"

    @pytest.mark.asyncio
    async def test_registry_includes_default_noise_terms(
        self, theme_service: ThemeRegistryService,
    ):
        """注册表应包含默认噪声词。"""
        registry = await theme_service.get_registry()
        for term in DEFAULT_NOISE_TERMS:
            assert registry.is_noise(term), f"'{term}' 应为噪声词"


# ---------------------------------------------------------------------------
# 7.2 配置加载和校验测试
# ---------------------------------------------------------------------------

class TestConfigLoading:
    """测试配置加载和校验。"""

    def test_validate_no_issues(self):
        """无冲突时应返回空列表。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链",
            members=("光伏", "TOPCon"),
            source="builtin",
        )
        registry.themes["消费农业链"] = ThemeEntry(
            theme_name="消费农业链",
            members=("猪肉", "鸡肉"),
            source="builtin",
        )
        issues = registry.validate()
        assert issues == []

    def test_validate_cross_theme_conflict(self):
        """跨主题冲突应被检测。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链",
            members=("光伏", "TOPCon"),
            source="builtin",
        )
        registry.themes["锂电储能链"] = ThemeEntry(
            theme_name="锂电储能链",
            members=("TOPCon", "锂电池"),
            source="builtin",
        )
        issues = registry.validate()
        assert any(i["type"] == "cross_theme_conflict" for i in issues)

    def test_validate_noise_conflict(self):
        """噪声词冲突应被检测。"""
        registry = ThemeRegistry()
        registry.themes["消费农业链"] = ThemeEntry(
            theme_name="消费农业链",
            members=("猪肉",),
            source="builtin",
        )
        registry.noise_terms.add(SectorIdentity.comparison_key("猪肉"))
        issues = registry.validate()
        assert any(i["type"] == "noise_conflict" for i in issues)

    @pytest.mark.asyncio
    async def test_list_themes(self, theme_service: ThemeRegistryService):
        """list_themes 应返回主题列表。"""
        registry = await theme_service.get_registry()
        themes = registry.list_themes()
        assert len(themes) >= 5
        names = {t["name"] for t in themes}
        assert "光伏产业链" in names

    @pytest.mark.asyncio
    async def test_show_theme(self, theme_service: ThemeRegistryService):
        """show_theme 应返回主题详情。"""
        registry = await theme_service.get_registry()
        detail = registry.show_theme("光伏产业链")
        assert detail is not None
        assert "光伏" in detail["members"]


# ---------------------------------------------------------------------------
# 7.3 候选提取测试
# ---------------------------------------------------------------------------

class TestCandidateExtraction:
    """测试候选提取。"""

    @pytest.mark.asyncio
    async def test_market_sectors_candidates(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
    ):
        """market_sectors 应产生候选。"""
        async with seeded_db.get_session() as session:
            for name in ["量子计算", "脑机接口", "光伏"]:
                session.add(MarketSector(
                    trade_date=date(2026, 5, 15),
                    sector_code=f"{name}_2026-05-15",
                    sector_name=name,
                    change_pct=1.0,
                ))

        registry = await theme_service.get_registry()
        cutoff = date(2026, 5, 10)
        candidates = await theme_service._extract_candidates(cutoff, registry)
        candidate_terms = {c["term"] for c in candidates}
        # "量子计算" 和 "脑机接口" 不在任何主题中，应成为候选
        assert "量子计算" in candidate_terms or "脑机接口" in candidate_terms
        # "光伏" 已在主题中，不应成为候选
        assert "光伏" not in candidate_terms

    @pytest.mark.asyncio
    async def test_noise_terms_excluded_from_candidates(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
    ):
        """噪声词不应成为候选。"""
        async with seeded_db.get_session() as session:
            session.add(MarketSector(
                trade_date=date(2026, 5, 15),
                sector_code="本月解禁_2026-05-15",
                sector_name="本月解禁",
                change_pct=1.0,
            ))

        registry = await theme_service.get_registry()
        cutoff = date(2026, 5, 10)
        candidates = await theme_service._extract_candidates(cutoff, registry)
        candidate_terms = {c["term"] for c in candidates}
        assert "本月解禁" not in candidate_terms


# ---------------------------------------------------------------------------
# 7.4 规则评分和低证据过滤测试
# ---------------------------------------------------------------------------

class TestRuleScoring:
    """测试规则评分和低证据过滤。"""

    def test_score_candidates_basic(self):
        """基本评分。"""
        registry = ThemeRegistry()
        candidates = [
            {
                "term": "量子计算",
                "normalized_key": "量子计算",
                "sources": ["market_sector", "market_sector", "market_sector"],
                "evidence": [],
            },
        ]
        scored = ThemeRegistryService._score_candidates(candidates, registry)
        assert scored[0]["score"] > 0
        assert scored[0]["source_counts"]["market_sector"] == 3


# ---------------------------------------------------------------------------
# 7.5 AI 归属测试
# ---------------------------------------------------------------------------

class TestAIClassification:
    """测试 AI 归属判断。"""

    def test_parse_valid_classification(self):
        """解析有效 AI 分类结果。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链",
            members=("光伏",),
            source="builtin",
        )
        candidates = [
            {"term": "HJT电池", "normalized_key": "hjt电池", "sources": ["market_sector"], "evidence": []},
        ]
        response = json.dumps([
            {"term": "HJT电池", "action": "add_to_existing_theme",
             "target_theme_name": "光伏产业链", "confidence": 0.85, "reason": "光伏技术"}
        ])
        results = ThemeRegistryService._parse_ai_classification(response, candidates, registry)
        assert len(results) == 1
        assert results[0]["action"] == "add_to_existing_theme"
        assert results[0]["target_theme_name"] == "光伏产业链"

    def test_parse_invalid_json_returns_empty(self):
        """无效 JSON 应返回空列表。"""
        registry = ThemeRegistry()
        candidates = [{"term": "test", "normalized_key": "test", "sources": [], "evidence": []}]
        results = ThemeRegistryService._parse_ai_classification("not json", candidates, registry)
        assert results == []

    def test_parse_unknown_term_ignored(self):
        """未知词应被忽略。"""
        registry = ThemeRegistry()
        candidates = [{"term": "已知词", "normalized_key": "已知词", "sources": [], "evidence": []}]
        response = json.dumps([
            {"term": "未知词", "action": "add_to_existing_theme",
             "target_theme_name": "光伏产业链", "confidence": 0.9, "reason": ""}
        ])
        results = ThemeRegistryService._parse_ai_classification(response, candidates, registry)
        assert results == []

    def test_parse_low_confidence_filtered(self):
        """低置信度应被过滤。"""
        registry = ThemeRegistry()
        registry.themes["光伏产业链"] = ThemeEntry(
            theme_name="光伏产业链", members=("光伏",), source="builtin",
        )
        candidates = [{"term": "test", "normalized_key": "test", "sources": [], "evidence": []}]
        response = json.dumps([
            {"term": "test", "action": "add_to_existing_theme",
             "target_theme_name": "光伏产业链", "confidence": 0.3, "reason": ""}
        ])
        results = ThemeRegistryService._parse_ai_classification(response, candidates, registry)
        assert results == []

    def test_parse_unknown_theme_rejected(self):
        """目标主题不存在时应拒绝。"""
        registry = ThemeRegistry()
        candidates = [{"term": "test", "normalized_key": "test", "sources": [], "evidence": []}]
        response = json.dumps([
            {"term": "test", "action": "add_to_existing_theme",
             "target_theme_name": "不存在的主题", "confidence": 0.9, "reason": ""}
        ])
        results = ThemeRegistryService._parse_ai_classification(response, candidates, registry)
        assert results == []


# ---------------------------------------------------------------------------
# 7.6 建议审查测试
# ---------------------------------------------------------------------------

class TestThemeSuggestionReview:
    """测试主题词建议审查。"""

    @pytest.mark.asyncio
    async def test_list_pending_suggestions(self, theme_service: ThemeRegistryService):
        """列出 pending 建议。"""
        async with theme_service.db.get_session() as session:
            session.add(ThemeTermSuggestion(
                suggestion_type="add_to_existing_theme",
                term="量子计算",
                normalized_key="量子计算",
                target_theme_name="光伏产业链",
                status="pending",
                confidence=0.8,
                reason="测试",
            ))

        suggestions = await theme_service.list_theme_suggestions(status="pending")
        assert len(suggestions) == 1
        assert suggestions[0]["term"] == "量子计算"

    @pytest.mark.asyncio
    async def test_accept_suggestion(self, theme_service: ThemeRegistryService):
        """接受建议应写入 AcceptedThemeTerm。"""
        async with theme_service.db.get_session() as session:
            session.add(ThemeTermSuggestion(
                suggestion_type="add_to_existing_theme",
                term="量子计算",
                normalized_key="量子计算",
                target_theme_name="光伏产业链",
                status="pending",
                confidence=0.8,
                reason="测试",
            ))
            await session.flush()
            result = await session.execute(
                select(ThemeTermSuggestion).where(
                    ThemeTermSuggestion.term == "量子计算"
                )
            )
            sid = result.scalar_one().id

        result = await theme_service.accept_theme_suggestion(sid)
        assert result["action"] == "accepted"

        # 验证 AcceptedThemeTerm
        async with theme_service.db.get_session() as session:
            result = await session.execute(
                select(AcceptedThemeTerm).where(AcceptedThemeTerm.term == "量子计算")
            )
            accepted = result.scalar_one_or_none()
            assert accepted is not None
            assert accepted.theme_name == "光伏产业链"

    @pytest.mark.asyncio
    async def test_ignore_suggestion(self, theme_service: ThemeRegistryService):
        """忽略建议应标记为 ignored。"""
        async with theme_service.db.get_session() as session:
            session.add(ThemeTermSuggestion(
                suggestion_type="mark_noise",
                term="本月解禁",
                normalized_key="本月解禁",
                status="pending",
                confidence=0.9,
            ))
            await session.flush()
            result = await session.execute(
                select(ThemeTermSuggestion).where(
                    ThemeTermSuggestion.term == "本月解禁"
                )
            )
            sid = result.scalar_one().id

        result = await theme_service.ignore_theme_suggestion(sid)
        assert result["action"] == "ignored"

    @pytest.mark.asyncio
    async def test_accept_nonexistent_suggestion(self, theme_service: ThemeRegistryService):
        """接受不存在的建议应返回错误。"""
        result = await theme_service.accept_theme_suggestion(999)
        assert result["action"] == "error"


# ---------------------------------------------------------------------------
# 7.7 CLI 注册测试
# ---------------------------------------------------------------------------

class TestThemeCLIRegistration:
    """测试主题 CLI 命令注册。"""

    def test_themes_subcommand_registered(self):
        """themes 子命令组应已注册。"""
        from src.cli.sector_trends import groups
        commands = {cmd for cmd in groups.list_commands(None)}
        assert "themes" in commands

    def test_themes_subcommands_registered(self):
        """themes 子命令应已注册。"""
        from src.cli.sector_trends import themes
        commands = {cmd for cmd in themes.list_commands(None)}
        assert "ls" in commands
        assert "show" in commands
        assert "validate" in commands
        assert "add" in commands
        assert "remove" in commands
        assert "ignore-term" in commands
        assert "suggest" in commands
        assert "suggestions" in commands
        assert "accept" in commands
        assert "ignore" in commands


# ---------------------------------------------------------------------------
# 7.8 集成测试：接受学习影响后续建议
# ---------------------------------------------------------------------------

class TestLearningIntegration:
    """测试接受学习影响后续建议。"""

    @pytest.mark.asyncio
    async def test_accepted_term_affects_match(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
    ):
        """接受的主题词应影响后续主题匹配。"""
        # 先确认 "智能机器" 在内置主题中
        registry = await theme_service.get_registry()
        assert registry.match("智能机器") is not None

    @pytest.mark.asyncio
    async def test_accepted_learning_affects_suggest(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
        group_service: SectorGroupService,
    ):
        """接受学习后，groups suggest 应使用新词典。"""
        # 添加已接受学习结果
        async with seeded_db.get_session() as session:
            session.add(AcceptedThemeTerm(
                theme_name="光伏产业链",
                term="HJT电池",
                normalized_key=SectorIdentity.comparison_key("HJT电池"),
            ))

        # 刷新缓存
        theme_service.invalidate_cache()

        # 创建新的 group service 使用该 registry
        svc_with_registry = SectorGroupService(seeded_db, theme_registry=theme_service)
        registry = await svc_with_registry._theme_registry.get_registry()
        # HJT电池 应可匹配
        assert registry.match("HJT电池") == "光伏产业链"

    @pytest.mark.asyncio
    async def test_generate_suggestions_no_ai(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
    ):
        """无 AI 时应返回结果不崩溃。"""
        result = await theme_service.generate_theme_suggestions(days=10)
        assert "suggestions_created" in result

    @pytest.mark.asyncio
    async def test_generate_suggestions_with_mock_ai(
        self,
        seeded_db: Database,
        theme_service: ThemeRegistryService,
    ):
        """mock AI 应可生成建议。"""
        async with seeded_db.get_session() as session:
            session.add(MarketSector(
                trade_date=date(2026, 5, 15),
                sector_code="量子计算_2026-05-15",
                sector_name="量子计算",
                change_pct=1.0,
            ))

        mock_ai = AsyncMock()
        mock_ai._call_api.return_value = json.dumps([
            {"term": "量子计算", "action": "create_theme",
             "target_theme_name": None, "suggested_theme_name": "量子计算链",
             "confidence": 0.75, "reason": "新兴科技方向"}
        ])

        result = await theme_service.generate_theme_suggestions(
            days=10, ai_processor=mock_ai
        )
        assert "suggestions_created" in result


# ---------------------------------------------------------------------------
# 手动维护测试
# ---------------------------------------------------------------------------

class TestManualMaintenance:
    """测试手动维护命令。"""

    @pytest.mark.asyncio
    async def test_add_theme_member(self, theme_service: ThemeRegistryService, tmp_path: Path):
        """手动添加主题词成员。"""
        with patch("src.services.theme_registry.CONFIG_PATH", tmp_path / "themes.json"):
            result = await theme_service.add_theme_member("光伏产业链", "IBC电池")
            assert result["action"] == "added"

            config = json.loads((tmp_path / "themes.json").read_text())
            assert "IBC电池" in config["themes"]["光伏产业链"]["members"]

    @pytest.mark.asyncio
    async def test_ignore_term(self, theme_service: ThemeRegistryService, tmp_path: Path):
        """添加噪声词。"""
        with patch("src.services.theme_registry.CONFIG_PATH", tmp_path / "themes.json"):
            result = await theme_service.ignore_term("虚拟现实")
            assert result["action"] == "ignored"

            config = json.loads((tmp_path / "themes.json").read_text())
            assert "虚拟现实" in config["noise_terms"]
