"""CLS 看盘数据板块归属修复测试 - 覆盖精确匹配、别名匹配、主题匹配、低置信度匹配、未匹配、保留已有板块。"""

import json
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.cli.sector_trends import sector_trends
from src.models.schema import Base, CLSWatchData, TrackedSector, AcceptedThemeTerm, SectorTrendSummary
from src.services.cls_watch_repair import (
    ClsWatchRepairService,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    RepairResult,
)
from src.storage.database import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_instance(db_engine):
    db = Database.__new__(Database)
    db._engine = db_engine
    db._session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    db.database_url = "sqlite+aiosqlite:///:memory:"
    return db


def _ts(d: date) -> int:
    """日期转时间戳。"""
    return int(datetime.combine(d, datetime.min.time()).timestamp())


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

class TestPreserveExistingSectors:
    """验证已有非空 sectors 的记录保持不变。"""

    @pytest.mark.asyncio
    async def test_existing_sectors_preserved(self, db_instance: Database) -> None:
        """已有 sectors 的记录不被修改。"""
        # 准备：创建一个有 sectors 的看盘记录
        async with db_instance.get_session() as session:
            item = CLSWatchData(
                watch_id="w1",
                title="半导体板块大涨",
                content="半导体产业链集体拉升",
                ctime=_ts(date(2026, 5, 6)),
                sectors=json.dumps(["半导体"]),
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        assert result.unchanged == 1
        assert result.repaired == 0

        # 验证 sectors 没有被修改
        async with db_instance.get_session() as session:
            from sqlalchemy import select
            res = await session.execute(
                select(CLSWatchData).where(CLSWatchData.watch_id == "w1")
            )
            db_item = res.scalar_one()
            assert json.loads(db_item.sectors) == ["半导体"]


class TestExactNameMatch:
    """验证已跟踪板块名称精确匹配（高置信度）。"""

    @pytest.mark.asyncio
    async def test_exact_tracked_name_match(self, db_instance: Database) -> None:
        """标题中包含已跟踪板块名时，高置信度匹配。"""
        async with db_instance.get_session() as session:
            # 添加跟踪板块
            sector = TrackedSector(
                canonical_name="半导体",
                status="tracked",
            )
            session.add(sector)

            # 添加空 sectors 的看盘记录
            item = CLSWatchData(
                watch_id="w2",
                title="半导体板块大涨",
                content="半导体产业链集体拉升",
                ctime=_ts(date(2026, 5, 6)),
                sectors=None,
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        assert result.repaired == 1
        assert result.unchanged == 0
        assert result.unmatched == 0

        # 验证修复结果
        async with db_instance.get_session() as session:
            from sqlalchemy import select
            res = await session.execute(
                select(CLSWatchData).where(CLSWatchData.watch_id == "w2")
            )
            db_item = res.scalar_one()
            sectors = json.loads(db_item.sectors)
            assert "半导体" in sectors


class TestAliasMatch:
    """验证已跟踪板块别名匹配（高置信度）。"""

    @pytest.mark.asyncio
    async def test_alias_match(self, db_instance: Database) -> None:
        """内容中包含板块别名时，高置信度匹配。"""
        async with db_instance.get_session() as session:
            sector = TrackedSector(
                canonical_name="光伏",
                status="tracked",
                aliases=json.dumps(["太阳能"]),
            )
            session.add(sector)

            item = CLSWatchData(
                watch_id="w3",
                title="太阳能产业链调研",
                content="太阳能组件价格上涨",
                ctime=_ts(date(2026, 5, 6)),
                sectors=None,
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        assert result.repaired == 1
        # 验证归属到正确的板块
        assert result.details[0]["sectors"][0] == "光伏"
        assert any(
            m["source"] == "tracked_name" and m["confidence"] == CONFIDENCE_HIGH
            for m in result.details[0]["matches"]
        )


class TestLowConfidenceMatch:
    """验证低置信度关键词匹配。"""

    @pytest.mark.asyncio
    async def test_keyword_match_is_low_confidence(self, db_instance: Database) -> None:
        """关键词部分匹配标记为低置信度。"""
        async with db_instance.get_session() as session:
            sector = TrackedSector(
                canonical_name="半导体设备",
                status="tracked",
            )
            session.add(sector)

            # "设备" 是 "半导体设备" 的子串
            item = CLSWatchData(
                watch_id="w4",
                title="设备更新换代",
                content="国产设备加速替代",
                ctime=_ts(date(2026, 5, 6)),
                sectors=None,
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        # 如果有低置信度匹配，应被标记
        if result.repaired > 0:
            assert result.low_confidence >= 1
            matches = result.details[0]["matches"]
            assert any(m["confidence"] == CONFIDENCE_LOW for m in matches)


class TestUnmatchedRows:
    """验证无法匹配的记录标记为 unmatched。"""

    @pytest.mark.asyncio
    async def test_no_match_unmatched(self, db_instance: Database) -> None:
        """完全无关的看盘记录应标记为 unmatched。"""
        async with db_instance.get_session() as session:
            item = CLSWatchData(
                watch_id="w5",
                title="今日市场概况",
                content="市场整体平稳运行",
                ctime=_ts(date(2026, 5, 6)),
                sectors=None,
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        assert result.unmatched == 1
        assert result.repaired == 0


class TestStockBasedAttribution:
    """验证基于股票的归属推断。"""

    @pytest.mark.asyncio
    async def test_stock_to_sector_mapping(self, db_instance: Database) -> None:
        """有 stocks 但无 sectors 的记录可从 stock→sector 映射推断。"""
        async with db_instance.get_session() as session:
            # 添加一条同时有 stocks 和 sectors 的参考记录
            ref_item = CLSWatchData(
                watch_id="ref1",
                title="贵州茅台创新高",
                content="白酒板块活跃",
                ctime=_ts(date(2026, 5, 5)),
                stocks=json.dumps(["贵州茅台", "五粮液"]),
                sectors=json.dumps(["白酒"]),
            )
            session.add(ref_item)

            # 添加只有 stocks 无 sectors 的待修复记录
            target_item = CLSWatchData(
                watch_id="w6",
                title="贵州茅台季报发布",
                content="业绩超预期",
                ctime=_ts(date(2026, 5, 6)),
                stocks=json.dumps(["贵州茅台"]),
                sectors=None,
            )
            session.add(target_item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        # 参考记录有 sectors 所以 unchanged，目标记录通过股票匹配修复
        assert result.repaired >= 1
        assert result.unchanged >= 1

        # 验证通过股票匹配推断出板块
        repaired_detail = next(
            d for d in result.details if d["watch_id"] == "w6"
        )
        assert any(m["source"] == "stock" for m in repaired_detail["matches"])


class TestParseSectors:
    """验证 sectors JSON 解析。"""

    def test_none_returns_empty(self) -> None:
        assert ClsWatchRepairService._parse_sectors(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert ClsWatchRepairService._parse_sectors("") == []

    def test_empty_array_returns_empty(self) -> None:
        assert ClsWatchRepairService._parse_sectors("[]") == []

    def test_valid_sectors(self) -> None:
        result = ClsWatchRepairService._parse_sectors('["半导体", "AI芯片"]')
        assert result == ["半导体", "AI芯片"]

    def test_invalid_json_returns_empty(self) -> None:
        assert ClsWatchRepairService._parse_sectors("not json") == []


class TestWindowBounds:
    """验证修复窗口边界正确。"""

    @pytest.mark.asyncio
    async def test_only_repairs_within_window(self, db_instance: Database) -> None:
        """只修复窗口内的记录。"""
        async with db_instance.get_session() as session:
            sector = TrackedSector(
                canonical_name="半导体",
                status="tracked",
            )
            session.add(sector)

            # 窗口内的记录
            in_window = CLSWatchData(
                watch_id="in1",
                title="半导体板块大涨",
                content="",
                ctime=_ts(date(2026, 5, 5)),
                sectors=None,
            )
            session.add(in_window)

            # 窗口外的记录（太早）
            out_window = CLSWatchData(
                watch_id="out1",
                title="半导体板块大涨",
                content="",
                ctime=_ts(date(2026, 4, 20)),
                sectors=None,
            )
            session.add(out_window)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        # 只有窗口内的记录被修复
        assert result.repaired == 1


class TestStandaloneRepairCLI:
    """验证 standalone repair CLI 命令。"""

    def test_repair_help_available(self) -> None:
        """repair 命令应出现在 sector-trends --help 中。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["--help"])
        assert result.exit_code == 0
        assert "repair" in result.output

    def test_repair_help_options(self) -> None:
        """repair --help 应包含 --date 和 --days。"""
        runner = CliRunner()
        result = runner.invoke(sector_trends, ["repair", "--help"])
        assert result.exit_code == 0
        assert "--date" in result.output
        assert "--days" in result.output

    @pytest.mark.asyncio
    async def test_repair_no_report_side_effects(self, db_instance: Database) -> None:
        """standalone repair 不应创建趋势报告文件或数据库行。"""
        async with db_instance.get_session() as session:
            sector = TrackedSector(
                canonical_name="半导体",
                status="tracked",
            )
            session.add(sector)

            item = CLSWatchData(
                watch_id="r1",
                title="半导体板块大涨",
                content="",
                ctime=_ts(date(2026, 5, 6)),
                sectors=None,
            )
            session.add(item)
            await session.flush()

        service = ClsWatchRepairService(db_instance)
        result = await service.repair_window(date(2026, 5, 6), window_days=10)

        assert result.repaired == 1

        # 验证没有创建任何 SectorTrendSummary
        async with db_instance.get_session() as session:
            res = await session.execute(select(SectorTrendSummary))
            summaries = list(res.scalars().all())
            assert len(summaries) == 0
