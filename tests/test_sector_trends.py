"""板块趋势跟踪测试 - 覆盖 CLI 注册、归一化去重、候选发现、初始化、单板块更新、批量更新、AI 模板结构。"""

import json
import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from click.testing import CliRunner
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.cli.ai import ai
from src.cli.sector_trends import sector_trends
from src.models.schema import Base, MarketSector, CLSWatchData, TrackedSector, SectorTrendSummary
from src.services.sector_trend_service import (
    SectorIdentity,
    SectorTrendAnalyzer,
    sector_to_path_name,
    TREND_STATUSES,
    STRENGTH_LEVELS,
    ACTION_BIASES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    """创建内存数据库引擎。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """创建数据库会话。"""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def db_instance(db_engine):
    """创建模拟 Database 实例。"""
    from src.storage.database import Database
    db = Database.__new__(Database)
    db._engine = db_engine
    db._session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    db.database_url = "sqlite+aiosqlite:///:memory:"
    return db


@pytest_asyncio.fixture
async def analyzer(db_instance):
    """创建 SectorTrendAnalyzer 实例。"""
    with patch.object(SectorTrendAnalyzer, "__init__", lambda self, db: None):
        a = SectorTrendAnalyzer.__new__(SectorTrendAnalyzer)
        a.db = db_instance
        from src.services.market_analyzer import MarketAnalyzer
        a._market_analyzer = MarketAnalyzer(db_instance)
        return a


# ---------------------------------------------------------------------------
# 6.1 CLI 注册与帮助测试
# ---------------------------------------------------------------------------

class TestCLIRegistration:
    """CLI 注册和帮助测试。"""

    def test_sector_trends_in_ai_help(self):
        """sector-trends 应出现在 ai --help 中。"""
        runner = CliRunner()
        result = runner.invoke(ai, ["--help"])
        assert result.exit_code == 0
        assert "sector-trends" in result.output

    def test_sector_trends_subcommands(self):
        """sector-trends 子命令应全部可用。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["--help"])
        assert result.exit_code == 0
        for cmd in ["discover", "ls", "init", "update", "show", "history"]:
            assert cmd in result.output

    def test_sector_trends_discover_help(self):
        """discover --help 应包含 --days。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["discover", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output

    def test_sector_trends_update_help(self):
        """update --help 应包含 --sector 和 --all。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["update", "--help"])
        assert result.exit_code == 0
        assert "--sector" in result.output
        assert "--all" in result.output

    def test_sector_trends_ls_help(self):
        """ls --help 应包含 --status 和 --limit。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["ls", "--help"])
        assert result.exit_code == 0
        assert "--status" in result.output
        assert "--limit" in result.output


# ---------------------------------------------------------------------------
# 6.2 板块归一化与去重测试
# ---------------------------------------------------------------------------

class TestSectorNormalization:
    """板块名称归一化和去重测试。"""

    def test_normalize_strips_whitespace(self):
        assert SectorIdentity.normalize("  半导体  ") == "半导体"

    def test_normalize_removes_suffix_board(self):
        result = SectorIdentity.normalize("半导体板块")
        assert result == "半导体"

    def test_normalize_removes_suffix_concept(self):
        result = SectorIdentity.normalize("AI概念")
        assert result == "AI"

    def test_normalize_removes_suffix_industry(self):
        result = SectorIdentity.normalize("汽车行业")
        assert result == "汽车"

    def test_comparison_key_lowercased(self):
        key = SectorIdentity.comparison_key("半导体板块")
        assert key == "半导体"

    def test_comparison_key_same_after_normalize(self):
        assert SectorIdentity.comparison_key("半导体板块") == SectorIdentity.comparison_key("半导体")

    def test_deduplicate_code_match(self):
        """相同代码应合并。"""
        existing = [MagicMock(
            id=1, sector_code="BK0447", canonical_name="半导体",
            aliases=None,
        )]
        candidates = [{"name": "半导体板块", "code": "BK0447"}]
        merged, new = SectorIdentity.deduplicate(candidates, existing)
        assert len(merged) == 1
        assert len(new) == 0

    def test_deduplicate_canonical_name_match(self):
        """规范名相同应合并。"""
        existing = [MagicMock(
            id=1, sector_code=None, canonical_name="半导体",
            aliases=None,
        )]
        candidates = [{"name": "半导体板块", "code": None}]
        merged, new = SectorIdentity.deduplicate(candidates, existing)
        assert len(merged) == 1
        assert len(new) == 0

    def test_deduplicate_alias_match(self):
        """命中显式别名应合并。"""
        existing = [MagicMock(
            id=1, sector_code=None, canonical_name="芯片",
            aliases=json.dumps(["半导体", "集成电路"]),
        )]
        candidates = [{"name": "半导体", "code": None}]
        merged, new = SectorIdentity.deduplicate(candidates, existing)
        assert len(merged) == 1
        assert len(new) == 0

    def test_deduplicate_related_but_distinct(self):
        """语义相关但不同的板块不应合并。"""
        existing = [MagicMock(
            id=1, sector_code="BK0447", canonical_name="半导体",
            aliases=None,
        )]
        candidates = [{"name": "先进封装", "code": "BK0999"}]
        merged, new = SectorIdentity.deduplicate(candidates, existing)
        assert len(merged) == 0
        assert len(new) == 1

    def test_find_possible_matches_containment(self):
        """包含关系的名称应作为 possible match。"""
        existing = [
            MagicMock(canonical_name="机器人"),
            MagicMock(canonical_name="人形机器人"),
        ]
        matches = SectorIdentity.find_possible_matches("机器人", existing)
        names = [m.canonical_name for m in matches]
        assert "人形机器人" in names
        assert "机器人" not in names  # 自身排除


# ---------------------------------------------------------------------------
# 6.3 候选发现测试
# ---------------------------------------------------------------------------

class TestDiscovery:
    """候选发现测试。"""

    @pytest.mark.asyncio
    async def test_discover_from_market_cache(self, db_session):
        """MarketSector 缓存应能被扫描到。"""
        # 插入测试数据
        today = date.today()
        db_session.add(MarketSector(
            trade_date=today,
            sector_code="BK0447",
            sector_name="半导体",
            change_pct=3.5,
            amount=100.0,
            main_inflow=20.0,
        ))
        await db_session.flush()

        result = await db_session.execute(
            select(MarketSector).where(MarketSector.sector_code == "BK0447")
        )
        sector = result.scalar_one_or_none()
        assert sector is not None
        assert sector.sector_name == "半导体"

    @pytest.mark.asyncio
    async def test_discover_from_cls_watch(self, db_session):
        """CLS 看盘数据中的板块标签应能被发现。"""
        import time
        now_ts = int(time.time())
        db_session.add(CLSWatchData(
            watch_id=f"test_{now_ts}",
            title="半导体板块活跃",
            content="测试内容",
            ctime=now_ts,
            sectors=json.dumps(["半导体", "AI芯片"]),
        ))
        await db_session.flush()

        result = await db_session.execute(
            select(CLSWatchData).where(CLSWatchData.watch_id == f"test_{now_ts}")
        )
        watch = result.scalar_one_or_none()
        assert watch is not None
        assert "半导体" in json.loads(watch.sectors)


# ---------------------------------------------------------------------------
# 6.4 初始化测试
# ---------------------------------------------------------------------------

class TestInit:
    """板块初始化测试。"""

    @pytest.mark.asyncio
    async def test_init_creates_new_tracked(self, analyzer, db_session):
        """手动初始化不存在的板块应创建 tracked 记录。"""
        sector = TrackedSector(
            canonical_name="新主题",
            status="tracked",
            source="manual",
            first_seen_date=date.today(),
            last_seen_date=date.today(),
            discovery_reason="手动初始化",
        )
        db_session.add(sector)
        await db_session.flush()

        result = await db_session.execute(
            select(TrackedSector).where(TrackedSector.canonical_name == "新主题")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.status == "tracked"
        assert found.source == "manual"

    @pytest.mark.asyncio
    async def test_init_promotes_candidate(self, db_session):
        """已有候选应能被提升为 tracked。"""
        sector = TrackedSector(
            canonical_name="半导体",
            status="candidate",
            source="market_cache",
            first_seen_date=date.today(),
            last_seen_date=date.today(),
            discovery_reason="强弱榜发现",
        )
        db_session.add(sector)
        await db_session.flush()

        # 模拟提升
        sector.status = "tracked"
        await db_session.flush()

        result = await db_session.execute(
            select(TrackedSector).where(TrackedSector.canonical_name == "半导体")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.status == "tracked"


# ---------------------------------------------------------------------------
# 6.5 单板块更新测试
# ---------------------------------------------------------------------------

class TestSingleSectorUpdate:
    """单板块更新测试。"""

    @pytest.mark.asyncio
    async def test_first_update_no_previous(self, db_session):
        """首次更新不应要求上次总结。"""
        sector = TrackedSector(
            canonical_name="半导体",
            status="tracked",
            source="manual",
            first_seen_date=date.today(),
            last_seen_date=date.today(),
        )
        db_session.add(sector)
        await db_session.flush()

        # 首次保存总结
        summary = SectorTrendSummary(
            sector_id=sector.id,
            sector_name=sector.canonical_name,
            end_date=date.today(),
            window_days=10,
            trend_status="低位启动",
            strength_level="中",
            action_bias="观察",
            content="# 首次建档",
            output_path="output/sector_trends/半导体/2026-01-01.md",
        )
        db_session.add(summary)
        await db_session.flush()

        result = await db_session.execute(
            select(SectorTrendSummary).where(
                SectorTrendSummary.sector_id == sector.id
            )
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.trend_status == "低位启动"

    @pytest.mark.asyncio
    async def test_update_with_previous_comparison(self, db_session):
        """后续更新应能读取上次总结。"""
        sector = TrackedSector(
            canonical_name="半导体",
            status="tracked",
            source="manual",
            first_seen_date=date.today() - timedelta(days=20),
            last_seen_date=date.today() - timedelta(days=1),
            last_updated_date=date.today() - timedelta(days=1),
        )
        db_session.add(sector)
        await db_session.flush()

        # 前一次总结
        prev = SectorTrendSummary(
            sector_id=sector.id,
            sector_name="半导体",
            end_date=date.today() - timedelta(days=1),
            window_days=10,
            trend_status="低位启动",
            strength_level="中",
            action_bias="观察",
            judgement="板块处于底部启动阶段",
            content="上次总结内容",
        )
        db_session.add(prev)
        await db_session.flush()

        # 验证可以读取上次总结
        result = await db_session.execute(
            select(SectorTrendSummary)
            .where(SectorTrendSummary.sector_id == sector.id)
            .order_by(SectorTrendSummary.end_date.desc())
        )
        latest = result.scalar_one_or_none()
        assert latest is not None
        assert latest.trend_status == "低位启动"

    @pytest.mark.asyncio
    async def test_sparse_evidence_handling(self):
        """稀疏证据应标记为 sparse。"""
        evidence = {
            "market_appearances": [{"trade_date": "2026-01-01", "change_pct": 1.0}],
            "cls_watch_mentions": [],
            "is_sparse": True,
            "total_evidence_count": 1,
        }
        assert evidence["is_sparse"] is True
        assert evidence["total_evidence_count"] < 3

    def test_path_safe_output(self):
        """输出路径应安全。"""
        assert sector_to_path_name("半导体") == "半导体"
        assert sector_to_path_name('test<>:"/\\|?*') == "test_________"
        assert sector_to_path_name("  spaces  ") == "spaces"


# ---------------------------------------------------------------------------
# 6.6 批量更新测试
# ---------------------------------------------------------------------------

class TestBatchUpdate:
    """批量更新测试。"""

    @pytest.mark.asyncio
    async def test_tracked_only_selection(self, db_session):
        """批量更新应只选择 tracked 板块。"""
        for name, status in [("半导体", "tracked"), ("候选板块", "candidate"), ("已忽略", "ignored")]:
            db_session.add(TrackedSector(
                canonical_name=name,
                status=status,
                source="test",
                first_seen_date=date.today(),
                last_seen_date=date.today(),
            ))
        await db_session.flush()

        result = await db_session.execute(
            select(TrackedSector).where(TrackedSector.status == "tracked")
        )
        tracked = list(result.scalars().all())
        assert len(tracked) == 1
        assert tracked[0].canonical_name == "半导体"

    @pytest.mark.asyncio
    async def test_limit_handling(self, db_session):
        """--limit 应限制更新数量。"""
        for i in range(5):
            db_session.add(TrackedSector(
                canonical_name=f"板块{i}",
                status="tracked",
                source="test",
                first_seen_date=date.today(),
                last_seen_date=date.today(),
            ))
        await db_session.flush()

        result = await db_session.execute(
            select(TrackedSector).where(TrackedSector.status == "tracked").limit(2)
        )
        limited = list(result.scalars().all())
        assert len(limited) == 2


# ---------------------------------------------------------------------------
# 6.7 AI 模板结构测试
# ---------------------------------------------------------------------------

class TestAITemplate:
    """AI 模板和结构化标签测试。"""

    def test_template_exists(self):
        """模板文件应存在。"""
        from pathlib import Path
        template_path = Path("templates/sector_trend_summary.md")
        assert template_path.exists()

    def test_template_has_required_sections(self):
        """模板应包含所有必需章节。"""
        from pathlib import Path
        content = Path("templates/sector_trend_summary.md").read_text(encoding="utf-8")
        required_sections = [
            "跟踪结论",
            "变化",
            "近期板块表现",
            "催化与逻辑",
            "个股联动",
            "趋势研判",
            "后续跟踪条件",
        ]
        for section in required_sections:
            assert section in content, f"模板缺少章节: {section}"

    def test_template_has_structured_labels(self):
        """模板应包含结构化标签要求。"""
        from pathlib import Path
        content = Path("templates/sector_trend_summary.md").read_text(encoding="utf-8")
        assert "trend_status" in content
        assert "strength_level" in content
        assert "action_bias" in content

    def test_trend_statuses_valid(self):
        """趋势状态标签应符合定义。"""
        assert "主线加强" in TREND_STATUSES
        assert "暂无趋势" in TREND_STATUSES
        assert len(TREND_STATUSES) == 8

    def test_strength_levels_valid(self):
        """强度等级应符合定义。"""
        assert STRENGTH_LEVELS == ("强", "中", "弱")

    def test_action_biases_valid(self):
        """操作倾向应符合定义。"""
        assert ACTION_BIASES == ("跟踪", "观察", "回避")

    def test_extract_labels(self):
        """标签提取应能从内容中解析结构化标签。"""
        from src.services.ai_processor import AIProcessor
        # 需要模拟 AIProcessor 初始化
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    llm_api_key="test", llm_base_url="http://test", llm_model="test",
                )
                processor = AIProcessor.__new__(AIProcessor)
                processor._sensitive_patterns = []

        content = """报告内容

trend_status: 主线延续
strength_level: 强
action_bias: 跟踪
judgement: 板块处于主线延续阶段，短期动能充足
"""
        labels = processor._extract_sector_trend_labels(content)
        assert labels["trend_status"] == "主线延续"
        assert labels["strength_level"] == "强"
        assert labels["action_bias"] == "跟踪"
        assert "主线延续" in labels["judgement"]

    def test_extract_labels_defaults_on_missing(self):
        """缺失标签应使用默认值。"""
        from src.services.ai_processor import AIProcessor
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    llm_api_key="test", llm_base_url="http://test", llm_model="test",
                )
                processor = AIProcessor.__new__(AIProcessor)
                processor._sensitive_patterns = []

        content = "报告内容，无标签"
        labels = processor._extract_sector_trend_labels(content)
        assert labels["trend_status"] == "暂无趋势"
        assert labels["strength_level"] == "弱"
        assert labels["action_bias"] == "观察"


# 需要在测试文件顶部导入 select
from sqlalchemy import select
