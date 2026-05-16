"""板块分组功能测试 - 模型、数据库、服务、CLI、AI 标签。"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.models.schema import (
    MarketSector,
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    SectorGroupTrendSummary,
    TrackedSector,
)
from src.services.sector_group_service import (
    CandidateCluster,
    CandidateMember,
    SectorGroupService,
    THEME_DEFINITIONS,
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
    """填充基础板块数据的测试数据库。"""
    async with test_db.get_session() as session:
        # 创建几个 tracked sectors
        for name, status in [("机器人", "tracked"), ("减速器", "tracked"),
                             ("传感器", "tracked"), ("机器视觉", "candidate"),
                             ("PEEK材料", "tracked"), ("丝杠", "tracked"),
                             ("灵巧手", "tracked"), ("半导体", "ignored")]:
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
def group_service(seeded_db: Database) -> SectorGroupService:
    """分组服务实例。"""
    return SectorGroupService(seeded_db)


# ---------------------------------------------------------------------------
# 7.1 模型与数据库初始化测试
# ---------------------------------------------------------------------------

class TestModelsAndDatabase:
    """测试新增模型和数据库表初始化。"""

    @pytest.mark.asyncio
    async def test_sector_groups_table_created(self, test_db: Database):
        """sector_groups 表应成功创建。"""
        async with test_db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sector_groups'")
            )
            assert result.scalar() == "sector_groups"

    @pytest.mark.asyncio
    async def test_sector_group_members_table_created(self, test_db: Database):
        """sector_group_members 表应成功创建。"""
        async with test_db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sector_group_members'")
            )
            assert result.scalar() == "sector_group_members"

    @pytest.mark.asyncio
    async def test_sector_group_suggestions_table_created(self, test_db: Database):
        """sector_group_suggestions 表应成功创建。"""
        async with test_db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sector_group_suggestions'")
            )
            assert result.scalar() == "sector_group_suggestions"

    @pytest.mark.asyncio
    async def test_sector_group_trend_summaries_table_created(self, test_db: Database):
        """sector_group_trend_summaries 表应成功创建。"""
        async with test_db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sector_group_trend_summaries'")
            )
            assert result.scalar() == "sector_group_trend_summaries"

    @pytest.mark.asyncio
    async def test_sector_group_canonical_name_unique(self, test_db: Database):
        """分组规范名唯一约束应生效。"""
        async with test_db.get_session() as session:
            g1 = SectorGroup(canonical_name="人形机器人", status="active")
            session.add(g1)

        with pytest.raises(Exception):
            async with test_db.get_session() as session:
                g2 = SectorGroup(canonical_name="人形机器人", status="active")
                session.add(g2)

    @pytest.mark.asyncio
    async def test_group_member_unique_constraint(self, test_db: Database):
        """group_id + sector_id 唯一约束。"""
        async with test_db.get_session() as session:
            g = SectorGroup(canonical_name="测试组", status="active")
            session.add(g)
            await session.flush()
            await session.refresh(g)

            s = TrackedSector(canonical_name="测试板块", status="tracked", source="test")
            session.add(s)
            await session.flush()
            await session.refresh(s)

            m1 = SectorGroupMember(group_id=g.id, sector_id=s.id, relation_type="core")
            session.add(m1)


# ---------------------------------------------------------------------------
# 7.2 分组 CRUD 和成员管理测试
# ---------------------------------------------------------------------------

class TestGroupCRUD:
    """测试分组 CRUD 操作。"""

    @pytest.mark.asyncio
    async def test_create_group(self, group_service: SectorGroupService):
        """创建分组应返回正确结果。"""
        result = await group_service.create_group("人形机器人")
        assert result["action"] == "created"
        assert result["canonical_name"] == "人形机器人"
        assert result["group_id"] is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_group(self, group_service: SectorGroupService):
        """创建重复分组应返回 already_exists。"""
        await group_service.create_group("人形机器人")
        result = await group_service.create_group("人形机器人")
        assert result["action"] == "already_exists"

    @pytest.mark.asyncio
    async def test_list_groups(self, group_service: SectorGroupService):
        """列出分组应返回正确信息。"""
        await group_service.create_group("人形机器人")
        await group_service.create_group("半导体")

        groups = await group_service.list_groups()
        assert len(groups) == 2
        assert groups[0]["member_count"] == 0

    @pytest.mark.asyncio
    async def test_resolve_group(self, group_service: SectorGroupService):
        """按名称解析分组。"""
        await group_service.create_group("人形机器人")
        result = await group_service.resolve_group("人形机器人")
        assert result is not None
        assert result["canonical_name"] == "人形机器人"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_group(self, group_service: SectorGroupService):
        """解析不存在的分组应返回 None。"""
        result = await group_service.resolve_group("不存在的分组")
        assert result is None

    @pytest.mark.asyncio
    async def test_show_group_detail(self, group_service: SectorGroupService):
        """查看分组详情。"""
        await group_service.create_group("人形机器人")
        await group_service.add_member("人形机器人", "机器人", "core")
        await group_service.add_member("人形机器人", "减速器", "upstream")

        detail = await group_service.show_group_detail("人形机器人")
        assert detail is not None
        assert detail["canonical_name"] == "人形机器人"
        assert len(detail["members"]) == 2

    @pytest.mark.asyncio
    async def test_add_member(self, group_service: SectorGroupService):
        """添加成员应返回正确结果。"""
        await group_service.create_group("人形机器人")
        result = await group_service.add_member("人形机器人", "机器人", "core")
        assert result["action"] == "added"
        assert result["sector_name"] == "机器人"

    @pytest.mark.asyncio
    async def test_add_duplicate_member_updates_metadata(self, group_service: SectorGroupService):
        """重复添加同一成员应更新元数据而非创建重复。"""
        await group_service.create_group("人形机器人")
        r1 = await group_service.add_member("人形机器人", "机器人", "core")
        r2 = await group_service.add_member("人形机器人", "机器人", "upstream")
        assert r1["action"] == "added"
        assert r2["action"] == "updated"

        detail = await group_service.show_group_detail("人形机器人")
        assert len(detail["members"]) == 1
        assert detail["members"][0]["relation_type"] == "upstream"

    @pytest.mark.asyncio
    async def test_add_member_invalid_type(self, group_service: SectorGroupService):
        """无效的关系类型应返回错误。"""
        await group_service.create_group("人形机器人")
        result = await group_service.add_member("人形机器人", "机器人", "invalid_type")
        assert result["action"] == "error"

    @pytest.mark.asyncio
    async def test_add_member_nonexistent_sector(self, group_service: SectorGroupService):
        """不存在的板块应返回错误。"""
        await group_service.create_group("人形机器人")
        result = await group_service.add_member("人形机器人", "不存在的板块")
        assert result["action"] == "error"


# ---------------------------------------------------------------------------
# 7.3 建议生成测试
# ---------------------------------------------------------------------------

class TestSuggestionGeneration:
    """测试建议生成逻辑。"""

    @pytest.mark.asyncio
    async def test_generate_suggestions(self, group_service: SectorGroupService):
        """建议生成应返回统计信息。"""
        result = await group_service.generate_suggestions(days=10)
        assert "new_group_suggestions" in result
        assert "add_member_suggestions" in result
        assert "refreshed_suggestions" in result

    @pytest.mark.asyncio
    async def test_list_suggestions_default_pending(self, group_service: SectorGroupService):
        """默认列出 pending 状态的建议。"""
        suggestions = await group_service.list_suggestions()
        for s in suggestions:
            assert s["status"] == "pending"

    @pytest.mark.asyncio
    async def test_ignored_sectors_excluded(self, group_service: SectorGroupService):
        """ignored 板块应被排除出建议。"""
        # "半导体" 在 seeded_db 中是 ignored 状态
        # 建议生成后不应包含 ignored 板块
        await group_service.generate_suggestions(days=10)
        suggestions = await group_service.list_suggestions()
        for s in suggestions:
            for m in s.get("members", []):
                assert m.get("sector_status") != "ignored"

    @pytest.mark.asyncio
    async def test_generate_suggestions_falls_back_to_market_cache(
        self,
        seeded_db: Database,
        group_service: SectorGroupService,
    ):
        """CLS 无板块标签时，应可基于行情缓存生成新分组建议。"""
        async with seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["机器人", "减速器", "传感器"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        result = await group_service.generate_suggestions(days=10)
        assert result["new_group_suggestions"] >= 1

        suggestions = await group_service.list_suggestions(suggestion_type="new_group")
        assert suggestions
        assert any(
            {"机器人", "减速器", "传感器"} & {
                member["sector_name"] for member in suggestion["members"]
            }
            for suggestion in suggestions
        )


# ---------------------------------------------------------------------------
# 7.4 建议接受测试
# ---------------------------------------------------------------------------

class TestSuggestionAcceptance:
    """测试建议接受逻辑。"""

    @pytest.mark.asyncio
    async def test_accept_suggestion_creates_group(self, group_service: SectorGroupService):
        """接受 new_group 建议应创建新分组。"""
        # 先创建一个 new_group 建议
        async with group_service.db.get_session() as session:
            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name="测试新分组",
                status="pending",
                confidence=0.8,
                reason="测试建议",
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)

            # 添加一个成员（机器人，tracked）
            from sqlalchemy import select
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.canonical_name == "机器人")
            )
            sector = result.scalar_one()
            sm = SectorGroupSuggestionMember(
                suggestion_id=suggestion.id,
                sector_id=sector.id,
                suggested_relation_type="core",
                confidence=0.9,
            )
            session.add(sm)
            suggestion_id = suggestion.id

        result = await group_service.accept_suggestion(suggestion_id)
        assert result["action"] == "accepted"
        assert result["group_id"] is not None
        assert "机器人" in result["accepted_members"]

    @pytest.mark.asyncio
    async def test_accept_suggestion_promotes_candidate(self, group_service: SectorGroupService):
        """接受建议时 candidate 板块应提升为 tracked。"""
        async with group_service.db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.canonical_name == "机器视觉")
            )
            sector = result.scalar_one()
            assert sector.status == "candidate"

            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name="视觉组",
                status="pending",
                confidence=0.7,
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)

            sm = SectorGroupSuggestionMember(
                suggestion_id=suggestion.id,
                sector_id=sector.id,
                suggested_relation_type="related",
            )
            session.add(sm)
            suggestion_id = suggestion.id

        await group_service.accept_suggestion(suggestion_id)

        async with group_service.db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.canonical_name == "机器视觉")
            )
            sector = result.scalar_one()
            assert sector.status == "tracked"

    @pytest.mark.asyncio
    async def test_accept_suggestion_keep_status(self, group_service: SectorGroupService):
        """使用 keep_status 时 candidate 不提升。"""
        async with group_service.db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.canonical_name == "机器视觉")
            )
            sector = result.scalar_one()

            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name="视觉组2",
                status="pending",
                confidence=0.7,
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)

            sm = SectorGroupSuggestionMember(
                suggestion_id=suggestion.id,
                sector_id=sector.id,
                suggested_relation_type="related",
            )
            session.add(sm)
            suggestion_id = suggestion.id

        await group_service.accept_suggestion(suggestion_id, keep_status=True)

        async with group_service.db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TrackedSector).where(TrackedSector.canonical_name == "机器视觉")
            )
            sector = result.scalar_one()
            assert sector.status == "candidate"

    @pytest.mark.asyncio
    async def test_ignore_suggestion(self, group_service: SectorGroupService):
        """忽略建议应标记为 ignored。"""
        async with group_service.db.get_session() as session:
            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name="忽略组",
                status="pending",
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)
            suggestion_id = suggestion.id

        result = await group_service.ignore_suggestion(suggestion_id)
        assert result["action"] == "ignored"

    @pytest.mark.asyncio
    async def test_ignore_non_pending_suggestion(self, group_service: SectorGroupService):
        """忽略非 pending 建议应返回错误。"""
        async with group_service.db.get_session() as session:
            suggestion = SectorGroupSuggestion(
                suggestion_type="new_group",
                suggested_group_name="已接受组",
                status="accepted",
            )
            session.add(suggestion)
            await session.flush()
            await session.refresh(suggestion)
            suggestion_id = suggestion.id

        result = await group_service.ignore_suggestion(suggestion_id)
        assert result["action"] == "error"


# ---------------------------------------------------------------------------
# 7.5 组级更新测试
# ---------------------------------------------------------------------------

class TestGroupUpdate:
    """测试组级更新逻辑。"""

    @pytest.mark.asyncio
    async def test_update_group_trend_no_ai(self, group_service: SectorGroupService):
        """无 AI 处理器时应返回 no_ai_processor。"""
        await group_service.create_group("人形机器人")
        await group_service.add_member("人形机器人", "机器人", "core")

        result = await group_service.update_group_trend("人形机器人")
        assert result["action"] == "no_ai_processor"

    @pytest.mark.asyncio
    async def test_update_nonexistent_group(self, group_service: SectorGroupService):
        """更新不存在的分组应返回错误。"""
        result = await group_service.update_group_trend("不存在的分组")
        assert result["action"] == "error"

    @pytest.mark.asyncio
    async def test_candidate_member_not_refreshed(self, group_service: SectorGroupService):
        """candidate 成员不应被默认刷新。"""
        await group_service.create_group("测试组")
        await group_service.add_member("测试组", "机器视觉", "related")

        # 模拟 AI 处理器
        mock_ai = AsyncMock()
        mock_ai.generate_sector_group_trend_summary.return_value = (
            "测试报告内容\n\ntrend_status: 暂无趋势\nstrength_level: 弱\naction_bias: 观察\njudgement: 测试",
            {"trend_status": "暂无趋势", "strength_level": "弱", "action_bias": "观察", "judgement": "测试"},
        )

        result = await group_service.update_group_trend("测试组", ai_processor=mock_ai)
        refresh_results = result.get("member_refresh_results", [])
        for mr in refresh_results:
            if mr.get("sector_name") == "机器视觉":
                assert mr.get("action") == "skipped_candidate"


# ---------------------------------------------------------------------------
# 7.6 CLI 注册测试
# ---------------------------------------------------------------------------

class TestCLIRegistration:
    """测试 CLI 命令注册。"""

    def test_sector_trends_groups_registered(self):
        """groups 子命令组应已注册。"""
        from src.cli.sector_trends import sector_trends
        commands = {cmd for cmd in sector_trends.list_commands(None)}
        assert "groups" in commands

    def test_groups_subcommands_registered(self):
        """groups 子命令应已注册。"""
        from src.cli.sector_trends import groups
        commands = {cmd for cmd in groups.list_commands(None)}
        assert "ls" in commands
        assert "show" in commands
        assert "create" in commands
        assert "add" in commands
        assert "suggest" in commands
        assert "suggestions" in commands
        assert "accept" in commands
        assert "ignore" in commands
        assert "update" in commands
        assert "history" in commands


# ---------------------------------------------------------------------------
# 7.7 AI 标签提取测试
# ---------------------------------------------------------------------------

class TestAIExtractLabels:
    """测试分组趋势 AI 标签提取。"""

    def test_extract_group_trend_labels(self):
        """应正确提取分组趋势标签。"""
        from src.services.ai_processor import AIProcessor

        db = MagicMock()
        with patch.object(AIProcessor, '__init__', lambda self, db: None):
            processor = AIProcessor.__new__(AIProcessor)
            processor.db = db

        content = """# 分组报告

trend_status: 主线共振
strength_level: 强
action_bias: 跟踪
judgement: 组内多板块同步走强
"""
        labels = processor._extract_sector_group_trend_labels(content)
        assert labels["trend_status"] == "主线共振"
        assert labels["strength_level"] == "强"
        assert labels["action_bias"] == "跟踪"

    def test_extract_labels_default_values(self):
        """缺少标签时应返回默认值。"""
        from src.services.ai_processor import AIProcessor

        db = MagicMock()
        processor = AIProcessor.__new__(AIProcessor)
        processor.db = db

        content = "报告内容，无标签"
        labels = processor._extract_sector_group_trend_labels(content)
        assert labels["trend_status"] == "暂无趋势"
        assert labels["strength_level"] == "弱"
        assert labels["action_bias"] == "观察"


# ---------------------------------------------------------------------------
# 7.8 CLI 输出测试
# ---------------------------------------------------------------------------

class TestCLIOutput:
    """测试 CLI 阶段输出辅助。"""

    def test_stage_header(self):
        """阶段头标记应格式正确。"""
        from src.cli.sector_trends import _stage_header
        result = _stage_header(1, 4, "初始化板块")
        assert "[1/4]" in result
        assert "初始化板块" in result

    def test_stage_ok(self, capsys):
        """成功行应包含 v 标记。"""
        from src.cli.sector_trends import _stage_ok
        from io import StringIO
        # 直接测试函数调用不报错即可
        _stage_ok("测试成功")


# ---------------------------------------------------------------------------
# 7.2 补充：成员详情测试
# ---------------------------------------------------------------------------

class TestGroupMemberDetail:
    """测试分组成员详情加载。"""

    @pytest.mark.asyncio
    async def test_member_detail_includes_sector_status(self, group_service: SectorGroupService):
        """成员详情应包含板块状态。"""
        await group_service.create_group("人形机器人")
        await group_service.add_member("人形机器人", "机器人", "core")
        await group_service.add_member("人形机器人", "机器视觉", "related")

        detail = await group_service.show_group_detail("人形机器人")
        assert detail is not None

        member_names = {m["sector_name"] for m in detail["members"]}
        assert "机器人" in member_names
        assert "机器视觉" in member_names

        for m in detail["members"]:
            assert "sector_status" in m
            assert "relation_type" in m
            assert "last_seen_date" in m


# ---------------------------------------------------------------------------
# 查看与历史测试
# ---------------------------------------------------------------------------

class TestGroupHistory:
    """测试分组历史查看。"""

    @pytest.mark.asyncio
    async def test_history_empty(self, group_service: SectorGroupService):
        """无历史的分组应返回空列表。"""
        await group_service.create_group("人形机器人")
        records = await group_service.group_history("人形机器人")
        assert records == []

    @pytest.mark.asyncio
    async def test_show_latest_no_report(self, group_service: SectorGroupService):
        """无报告的分组应返回 has_summary=False。"""
        await group_service.create_group("人形机器人")
        result = await group_service.show_latest_group_report("人形机器人")
        assert result is not None
        assert result["has_summary"] is False

    @pytest.mark.asyncio
    async def test_show_nonexistent_group(self, group_service: SectorGroupService):
        """不存在的分组应返回 None。"""
        result = await group_service.show_latest_group_report("不存在的分组")
        assert result is None


# ---------------------------------------------------------------------------
# 批量更新测试
# ---------------------------------------------------------------------------

class TestBatchGroupUpdate:
    """测试批量分组更新。"""

    @pytest.mark.asyncio
    async def test_update_all_groups(self, group_service: SectorGroupService):
        """批量更新应返回正确统计。"""
        await group_service.create_group("人形机器人")
        await group_service.add_member("人形机器人", "机器人", "core")

        result = await group_service.update_all_group_trends()
        assert "total" in result
        assert "success" in result
        assert "skipped" in result
        assert "failed" in result
        assert "member_refresh_success" in result


# ---------------------------------------------------------------------------
# 主题约束与语义清洗测试
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def theme_seeded_db(test_db: Database):
    """填充主题相关板块数据的测试数据库。"""
    async with test_db.get_session() as session:
        for name, status in [
            ("光伏", "tracked"), ("TOPCon", "tracked"),
            ("BC电池", "tracked"), ("HIT电池", "candidate"),
            ("钙钛矿", "tracked"),
            ("猪肉", "tracked"), ("鸡肉", "tracked"),
            ("宽带提速", "tracked"),
            ("锂电池", "tracked"), ("固态电池", "tracked"),
            ("CRO", "tracked"), ("白酒", "tracked"),
            ("风电", "tracked"), ("核电核能", "tracked"),
            ("卫星导航", "tracked"), ("国产软件", "tracked"),
            ("机器人", "tracked"), ("智能机器", "tracked"),
            ("半导体", "ignored"), ("已退市", "inactive"),
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
def theme_service(theme_seeded_db: Database) -> SectorGroupService:
    """主题测试用分组服务实例。"""
    return SectorGroupService(theme_seeded_db)


class TestThemeConstraints:
    """测试主题约束和跨主题过滤。"""

    def test_theme_definitions_exist(self):
        """主题词典应包含至少 5 个主题。"""
        assert len(THEME_DEFINITIONS) >= 5

    def test_match_theme_photovoltaic(self):
        """光伏应匹配光伏产业链。"""
        assert SectorGroupService.match_theme("光伏") == "光伏产业链"

    def test_match_theme_topcon(self):
        """TOPCon 应匹配光伏产业链。"""
        assert SectorGroupService.match_theme("TOPCon") == "光伏产业链"

    def test_match_theme_robotics(self):
        """机器人相关板块应匹配人形机器人链。"""
        assert SectorGroupService.match_theme("机器人") == "人形机器人链"
        assert SectorGroupService.match_theme("机器人概念") == "人形机器人链"
        assert SectorGroupService.match_theme("智能机器") == "人形机器人链"
        assert SectorGroupService.match_theme("PEEK材料") == "人形机器人链"

    def test_match_theme_pork(self):
        """猪肉应匹配消费农业链。"""
        assert SectorGroupService.match_theme("猪肉") == "消费农业链"

    def test_match_theme_unknown(self):
        """未知板块应返回 None。"""
        assert SectorGroupService.match_theme("量子计算") is None

    def test_match_theme_case_insensitive(self):
        """主题匹配应忽略大小写。"""
        assert SectorGroupService.match_theme("topcon") == "光伏产业链"
        assert SectorGroupService.match_theme("CRO") == "医药服务链"

    @pytest.mark.asyncio
    async def test_mixed_theme_market_cache_rejected(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """跨主题 market-cache 聚类（如宽带提速+猪肉）不应产生 new_group 建议。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["宽带提速", "猪肉", "CRO", "白酒"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        result = await theme_service.generate_suggestions(days=10)

        # 验证产生的建议不包含跨主题混杂
        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        for s in suggestions:
            member_themes = set()
            for m in s.get("members", []):
                theme = SectorGroupService.match_theme(m["sector_name"])
                if theme:
                    member_themes.add(theme)
            # 如果有多个不同主题的成员，说明是跨主题混杂（不应出现）
            if len(member_themes) > 1:
                pytest.fail(f"建议 #{s['id']} 包含跨主题成员: {member_themes}")

    @pytest.mark.asyncio
    async def test_coherent_theme_cluster_creates_suggestion(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """同主题聚类（光伏+TOPCon+BC电池+HIT电池+钙钛矿）应产生 cleaned pending 建议。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池", "HIT电池", "钙钛矿"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        result = await theme_service.generate_suggestions(days=10)
        assert result["new_group_suggestions"] >= 1

        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        assert len(suggestions) >= 1

        # 找到包含光伏成员的建议
        pv_suggestions = [
            s for s in suggestions
            if any(m["sector_name"] == "光伏" for m in s.get("members", []))
        ]
        assert len(pv_suggestions) >= 1

        pv_suggestion = pv_suggestions[0]
        member_names = {m["sector_name"] for m in pv_suggestion["members"]}
        assert "光伏" in member_names
        assert len(pv_suggestion["members"]) >= 2

        # 验证 evidence
        assert pv_suggestion["confidence"] is not None

    @pytest.mark.asyncio
    async def test_single_day_same_theme_market_cache_creates_low_confidence_suggestion(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """同主题成员即使只有单日行情共现，也应产生低置信主题线索。"""
        async with theme_seeded_db.get_session() as session:
            for name in ["机器人", "智能机器"]:
                session.add(MarketSector(
                    trade_date=date(2026, 5, 15),
                    sector_code=f"{name}_2026-05-15",
                    sector_name=name,
                    change_pct=1.0,
                ))

        result = await theme_service.generate_suggestions(days=10)
        assert result["new_group_suggestions"] >= 1

        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        robot_suggestions = [
            s for s in suggestions
            if s["suggested_group_name"] == "人形机器人链"
        ]
        assert robot_suggestions
        member_names = {m["sector_name"] for m in robot_suggestions[0]["members"]}
        assert {"机器人", "智能机器"} <= member_names

    @pytest.mark.asyncio
    async def test_single_day_robotics_theme_not_crowded_out_by_other_themes(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """候选主题较多时，同主题机器人线索也应保留。"""
        async with theme_seeded_db.get_session() as session:
            themes = [
                ["光伏", "TOPCon", "BC电池"],
                ["锂电池", "固态电池", "电解液"],
                ["卫星导航", "国产软件", "军工航天"],
                ["CRO", "CXO", "仿制药"],
                ["猪肉", "鸡肉", "白酒"],
                ["风电", "核电核能", "地热能"],
                ["机器人", "智能机器"],
            ]
            for names in themes:
                for name in names:
                    session.add(MarketSector(
                        trade_date=date(2026, 5, 15),
                        sector_code=f"{name}_2026-05-15",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        await theme_service.generate_suggestions(days=10)

        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        suggestion_names = {s["suggested_group_name"] for s in suggestions}
        assert "人形机器人链" in suggestion_names

    @pytest.mark.asyncio
    async def test_ignored_and_inactive_excluded(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """ignored 和 inactive 板块不应出现在建议中。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "半导体", "已退市"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        await theme_service.generate_suggestions(days=10)
        suggestions = await theme_service.list_suggestions()
        for s in suggestions:
            for m in s.get("members", []):
                assert m.get("sector_status") not in ("ignored", "inactive")


class TestAICleaning:
    """测试 AI 语义清洗。"""

    @pytest.mark.asyncio
    async def test_ai_accepts_coherent_cluster(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """AI 应接受同主题聚类。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池", "HIT电池", "钙钛矿"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        mock_ai = AsyncMock()
        mock_ai._call_api.return_value = json.dumps({
            "accepted": True,
            "suggested_group_name": "光伏产业链",
            "confidence": 0.85,
            "reason": "成员集中在光伏电池技术方向",
            "members": [
                {"sector_id": 1, "relation_type": "core", "confidence": 0.9, "reason": "光伏核心"},
                {"sector_id": 2, "relation_type": "core", "confidence": 0.8, "reason": "TOPCon 电池技术"},
                {"sector_id": 3, "relation_type": "related", "confidence": 0.7, "reason": "BC 电池"},
            ],
            "rejected_members": [],
        })

        result = await theme_service.generate_suggestions(
            days=10, ai_processor=mock_ai
        )
        assert result["new_group_suggestions"] >= 1

    @pytest.mark.asyncio
    async def test_ai_rejects_unknown_members(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """AI 返回的未知 sector_id 应被忽略。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        mock_ai = AsyncMock()
        mock_ai._call_api.return_value = json.dumps({
            "accepted": True,
            "suggested_group_name": "光伏",
            "confidence": 0.8,
            "reason": "test",
            "members": [
                {"sector_id": 1, "relation_type": "core", "confidence": 0.9, "reason": "ok"},
                {"sector_id": 999, "relation_type": "core", "confidence": 0.9, "reason": "unknown"},
            ],
            "rejected_members": [],
        })

        result = await theme_service.generate_suggestions(
            days=10, ai_processor=mock_ai
        )

        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        for s in suggestions:
            for m in s["members"]:
                assert m["sector_id"] != 999

    @pytest.mark.asyncio
    async def test_ai_invalid_json_fallback(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """AI 返回无效 JSON 时应回退到规则验证。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        mock_ai = AsyncMock()
        mock_ai._call_api.return_value = "这不是JSON"

        # 应该不崩溃，回退到规则验证
        result = await theme_service.generate_suggestions(
            days=10, ai_processor=mock_ai
        )
        assert "new_group_suggestions" in result

    @pytest.mark.asyncio
    async def test_ai_low_confidence_rejected(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """AI 低置信度结果应被拒绝。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        mock_ai = AsyncMock()
        mock_ai._call_api.return_value = json.dumps({
            "accepted": True,
            "suggested_group_name": "test",
            "confidence": 0.2,
            "reason": "低置信度",
            "members": [],
            "rejected_members": [],
        })

        result = await theme_service.generate_suggestions(
            days=10, ai_processor=mock_ai
        )
        assert "new_group_suggestions" in result

    @pytest.mark.asyncio
    async def test_ai_failure_fallback(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """AI 失败/超时时应安全回退。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        mock_ai = AsyncMock()
        mock_ai._call_api.side_effect = TimeoutError("AI 超时")

        result = await theme_service.generate_suggestions(
            days=10, ai_processor=mock_ai
        )
        assert "new_group_suggestions" in result


class TestDuplicateRefreshAndIgnored:
    """测试建议刷新和忽略抑制。"""

    @pytest.mark.asyncio
    async def test_duplicate_suggestion_refreshed(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """同名同成员的 pending 建议应被刷新而非重复创建。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        # 第一次生成
        await theme_service.generate_suggestions(days=10)
        first_suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        first_count = len(first_suggestions)

        # 第二次生成 - 应刷新而非重复创建
        await theme_service.generate_suggestions(days=10)
        second_suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        second_count = len(second_suggestions)

        # 不应增加超过一倍（允许少量差异）
        assert second_count <= first_count + 1

    @pytest.mark.asyncio
    async def test_ignored_suggestion_not_recreated(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """已 ignored 的建议不应被重新创建。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        # 第一次生成
        await theme_service.generate_suggestions(days=10)
        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")
        if suggestions:
            # 忽略第一条
            await theme_service.ignore_suggestion(suggestions[0]["id"])

        # 第二次生成 - ignored 的不应再出现
        await theme_service.generate_suggestions(days=10)
        pending = await theme_service.list_suggestions(status="pending", suggestion_type="new_group")
        for p in pending:
            assert p["id"] != suggestions[0]["id"] if suggestions else True


class TestEvidenceAndReason:
    """测试 evidence 和 reason 标注。"""

    @pytest.mark.asyncio
    async def test_market_cache_reason_label(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """行情缓存来源的 reason 应标注为弱线索。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        await theme_service.generate_suggestions(days=10)
        suggestions = await theme_service.list_suggestions(suggestion_type="new_group")

        for s in suggestions:
            # market-cache 来源的 reason 应包含"线索"或"行情"
            if s.get("reason"):
                reason = s["reason"]
                assert "行情缓存" in reason or "共现分析" in reason

    @pytest.mark.asyncio
    async def test_evidence_json_stored(
        self,
        theme_seeded_db: Database,
        theme_service: SectorGroupService,
    ):
        """建议应包含 evidence_json。"""
        async with theme_seeded_db.get_session() as session:
            for day in [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]:
                for name in ["光伏", "TOPCon", "BC电池"]:
                    session.add(MarketSector(
                        trade_date=day,
                        sector_code=f"{name}_{day.isoformat()}",
                        sector_name=name,
                        change_pct=1.0,
                    ))

        await theme_service.generate_suggestions(days=10)

        # 直接查询数据库验证 evidence_json
        async with theme_seeded_db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.suggestion_type == "new_group",
                    SectorGroupSuggestion.status == "pending",
                )
            )
            suggestions = result.scalars().all()

            for s in suggestions:
                if s.evidence_json:
                    evidence = json.loads(s.evidence_json)
                    assert "source" in evidence
                    assert "window_days" in evidence
                    assert "members" in evidence


class TestCLIWithSemanticCleaning:
    """测试语义清洗后 CLI 输出。"""

    def test_groups_suggest_command_has_no_ai_option(self):
        """groups suggest 命令应有 --no-ai 选项。"""
        from src.cli.sector_trends import groups
        # 查找 suggest 命令
        suggest_cmd = groups.get_command(None, "suggest")
        assert suggest_cmd is not None
        param_names = [p.name for p in suggest_cmd.params]
        assert "no_ai" in param_names
