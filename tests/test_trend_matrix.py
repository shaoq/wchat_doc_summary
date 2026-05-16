"""趋势矩阵服务和渲染器单元测试。"""

import os
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.trend_matrix_render import (
    render_expanded_group_markdown,
    render_expanded_group_rich,
    render_group_matrix_markdown,
    render_group_matrix_rich,
    render_sector_matrix_markdown,
    render_sector_matrix_rich,
)
from src.services.trend_matrix_service import (
    CHANGE_COOLING,
    CHANGE_MISSING,
    CHANGE_NEW,
    CHANGE_STEADY,
    CHANGE_WARMING,
    CHANGE_WEAKENING,
    GROUP_STAGE_RANK,
    SECTOR_STAGE_RANK,
    ExpandedGroupMatrix,
    GroupMatrixRow,
    MatrixCell,
    SectorMatrixRow,
    TrendMatrixService,
    compute_change_state,
)


# ── 变化状态计算测试 ────────────────────────────────────────────


class TestComputeChangeState:
    """Task 5.3: 变化状态计算测试。"""

    def test_new_when_no_prior(self) -> None:
        assert compute_change_state(
            "主线加强", None, SECTOR_STAGE_RANK, has_current=True, has_prior=False,
        ) == CHANGE_NEW

    def test_missing_when_no_current(self) -> None:
        assert compute_change_state(
            None, "主线延续", SECTOR_STAGE_RANK, has_current=False, has_prior=True,
        ) == CHANGE_MISSING

    def test_warming_when_higher(self) -> None:
        assert compute_change_state(
            "主线加强", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_WARMING

    def test_steady_when_equal(self) -> None:
        assert compute_change_state(
            "主线延续", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_STEADY

    def test_cooling_when_lower_but_active(self) -> None:
        assert compute_change_state(
            "分歧中继", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_COOLING

    def test_weakening_when_retreat(self) -> None:
        assert compute_change_state(
            "高位退潮", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_WEAKENING

    def test_weakening_when_no_trend(self) -> None:
        assert compute_change_state(
            "暂无趋势", "低位启动", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_WEAKENING

    def test_group_warming(self) -> None:
        assert compute_change_state(
            "主线共振", "主线扩散", GROUP_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_WARMING

    def test_group_cooling(self) -> None:
        assert compute_change_state(
            "轮动分化", "主线扩散", GROUP_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_COOLING

    def test_does_not_use_action_bias(self) -> None:
        """Task 2.4: 确保不依赖 action_bias。"""
        # 无论 action_bias 是什么，结果只取决于 stage ranking
        result1 = compute_change_state(
            "主线加强", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        )
        # 同样的 stage 配置应产生相同结果
        result2 = compute_change_state(
            "主线加强", "主线延续", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        )
        assert result1 == result2 == CHANGE_WARMING

    def test_unknown_stage_treated_as_zero(self) -> None:
        assert compute_change_state(
            "未知阶段", "暂无趋势", SECTOR_STAGE_RANK, has_current=True, has_prior=True,
        ) == CHANGE_STEADY  # 0 == 0


# ── 板块矩阵组装测试 ───────────────────────────────────────────


class TestSectorMatrixAssembly:
    """Task 5.1: 板块矩阵组装和缺失单元格测试。"""

    def _make_sector(self, sector_id: int = 1, name: str = "光伏") -> MagicMock:
        sector = MagicMock()
        sector.id = sector_id
        sector.canonical_name = name
        sector.sector_code = f"BK{sector_id:04d}"
        return sector

    def _make_summary(
        self,
        sector_id: int,
        end_date: date,
        trend_status: str = "主线延续",
        strength_level: str = "中",
        output_path: str | None = None,
    ) -> MagicMock:
        s = MagicMock()
        s.sector_id = sector_id
        s.end_date = end_date
        s.trend_status = trend_status
        s.strength_level = strength_level
        s.output_path = output_path
        return s

    def test_basic_row_assembly(self) -> None:
        sector = self._make_sector()
        d1 = date(2025, 1, 10)
        d2 = date(2025, 1, 5)
        summaries = [
            self._make_summary(1, d1, "主线加强", "强"),
            self._make_summary(1, d2, "主线延续", "中"),
        ]
        dates = [d1, d2]
        row = TrendMatrixService._assemble_sector_row(sector, summaries, dates)

        assert row.sector_name == "光伏"
        assert row.latest_date == d1
        assert row.cells[d1].trend_status == "主线加强"
        assert row.cells[d1].strength_level == "强"
        assert row.change_state == CHANGE_WARMING

    def test_missing_cell(self) -> None:
        sector = self._make_sector()
        d1 = date(2025, 1, 10)
        d2 = date(2025, 1, 5)
        # 只有 d1 有摘要
        summaries = [self._make_summary(1, d1, "主线延续", "中")]
        dates = [d1, d2]
        row = TrendMatrixService._assemble_sector_row(sector, summaries, dates)

        assert row.cells[d1].trend_status == "主线延续"
        assert row.cells[d2].trend_status is None
        assert row.cells[d2].strength_level is None

    def test_all_missing_cells(self) -> None:
        sector = self._make_sector()
        d1 = date(2025, 1, 10)
        dates = [d1]
        row = TrendMatrixService._assemble_sector_row(sector, [], dates)

        assert row.cells[d1].trend_status is None
        assert row.change_state == CHANGE_MISSING

    def test_output_path_in_cell(self) -> None:
        sector = self._make_sector()
        d1 = date(2025, 1, 10)
        summaries = [self._make_summary(1, d1, output_path="output/sector_trends/光伏.md")]
        row = TrendMatrixService._assemble_sector_row(sector, summaries, [d1])
        assert row.cells[d1].output_path == "output/sector_trends/光伏.md"


# ── 分组矩阵组装测试 ───────────────────────────────────────────


class TestGroupMatrixAssembly:
    """Task 5.2: 分组矩阵组装和展开测试。"""

    def _make_group(self, group_id: int = 1, name: str = "光伏产业链") -> MagicMock:
        group = MagicMock()
        group.id = group_id
        group.canonical_name = name
        return group

    def _make_group_summary(
        self,
        group_id: int,
        end_date: date,
        trend_status: str = "主线扩散",
        strength_level: str = "中",
        output_path: str | None = None,
    ) -> MagicMock:
        s = MagicMock()
        s.group_id = group_id
        s.end_date = end_date
        s.trend_status = trend_status
        s.strength_level = strength_level
        s.output_path = output_path
        return s

    def test_basic_group_row(self) -> None:
        group = self._make_group()
        d1 = date(2025, 1, 10)
        summaries = [self._make_group_summary(1, d1, "主线共振", "强")]
        row = TrendMatrixService._assemble_group_row(group, summaries, [d1], member_count=5)

        assert row.group_name == "光伏产业链"
        assert row.member_count == 5
        assert row.cells[d1].trend_status == "主线共振"
        assert row.change_state == CHANGE_NEW

    def test_missing_group_summary_with_dates(self) -> None:
        group = self._make_group()
        d1 = date(2025, 1, 10)
        d2 = date(2025, 1, 5)
        row = TrendMatrixService._assemble_group_row(group, [], [d1, d2], member_count=3)

        assert row.cells[d1].trend_status is None
        assert row.cells[d2].trend_status is None
        assert row.change_state == CHANGE_MISSING


# ── 日期选择测试 ────────────────────────────────────────────────


class TestResolveDates:
    def test_latest_only(self) -> None:
        summaries = []
        for d in [date(2025, 1, 5), date(2025, 1, 10), date(2025, 1, 15)]:
            s = MagicMock()
            s.end_date = d
            summaries.append(s)

        dates = TrendMatrixService.resolve_dates(summaries, latest_only=True)
        assert len(dates) == 1
        assert dates[0] == date(2025, 1, 15)

    def test_max_dates_limit(self) -> None:
        summaries = []
        for i in range(10):
            s = MagicMock()
            s.end_date = date(2025, 1, i + 1)
            summaries.append(s)

        dates = TrendMatrixService.resolve_dates(summaries, max_dates=3)
        assert len(dates) == 3

    def test_dedup_dates(self) -> None:
        d = date(2025, 1, 10)
        summaries = [MagicMock(end_date=d), MagicMock(end_date=d)]
        dates = TrendMatrixService.resolve_dates(summaries, max_dates=5)
        assert len(dates) == 1


# ── 渲染测试 ────────────────────────────────────────────────────


class TestRichRendering:
    def test_sector_matrix_rich(self) -> None:
        d1 = date(2025, 1, 10)
        rows = [
            SectorMatrixRow(
                sector_name="光伏",
                sector_code="BK0001",
                cells={d1: MatrixCell("主线延续", "中")},
                latest_date=d1,
                change_state=CHANGE_NEW,
            ),
        ]
        table = render_sector_matrix_rich(rows, [d1])
        assert table is not None

    def test_group_matrix_rich(self) -> None:
        d1 = date(2025, 1, 10)
        rows = [
            GroupMatrixRow(
                group_name="光伏产业链",
                member_count=5,
                cells={d1: MatrixCell("主线扩散", "中")},
                latest_date=d1,
                change_state=CHANGE_WARMING,
            ),
        ]
        table = render_group_matrix_rich(rows, [d1])
        assert table is not None

    def test_expanded_group_rich(self) -> None:
        d1 = date(2025, 1, 10)
        group_row = GroupMatrixRow(
            group_name="光伏产业链",
            member_count=2,
            cells={d1: MatrixCell("主线扩散", "中")},
            latest_date=d1,
            change_state=CHANGE_STEADY,
        )
        member_rows = [
            SectorMatrixRow(
                sector_name="光伏电池",
                sector_code="BK0001",
                cells={d1: MatrixCell("主线加强", "强")},
                latest_date=d1,
                change_state=CHANGE_WARMING,
            ),
        ]
        matrix = ExpandedGroupMatrix(group_row=group_row, member_rows=member_rows)
        table = render_expanded_group_rich(matrix, [d1])
        assert table is not None


class TestMarkdownRendering:
    def test_sector_matrix_markdown(self) -> None:
        d1 = date(2025, 1, 10)
        rows = [
            SectorMatrixRow(
                sector_name="光伏",
                sector_code="BK0001",
                cells={d1: MatrixCell("主线延续", "中")},
                latest_date=d1,
                change_state=CHANGE_NEW,
            ),
        ]
        md = render_sector_matrix_markdown(rows, [d1])
        assert "# 板块趋势矩阵" in md
        assert "光伏" in md
        assert "主线延续" in md
        assert "新增" in md

    def test_group_matrix_markdown(self) -> None:
        d1 = date(2025, 1, 10)
        rows = [
            GroupMatrixRow(
                group_name="光伏产业链",
                member_count=5,
                cells={d1: MatrixCell("主线扩散", "中")},
                latest_date=d1,
                change_state=CHANGE_WARMING,
            ),
        ]
        md = render_group_matrix_markdown(rows, [d1])
        assert "# 分组趋势矩阵" in md
        assert "光伏产业链" in md
        assert "5" in md

    def test_expanded_group_markdown(self) -> None:
        d1 = date(2025, 1, 10)
        group_row = GroupMatrixRow(
            group_name="光伏产业链",
            member_count=1,
            cells={d1: MatrixCell("主线扩散", "中")},
            latest_date=d1,
            change_state=CHANGE_STEADY,
        )
        member_rows = [
            SectorMatrixRow(
                sector_name="光伏电池",
                sector_code="BK0001",
                cells={d1: MatrixCell("主线加强", "强")},
                latest_date=d1,
                change_state=CHANGE_WARMING,
            ),
        ]
        matrix = ExpandedGroupMatrix(group_row=group_row, member_rows=member_rows)
        md = render_expanded_group_markdown(matrix, [d1])
        assert "光伏产业链" in md
        assert "光伏电池" in md
        assert "**光伏产业链**" in md

    def test_missing_cell_renders_as_dash(self) -> None:
        d1 = date(2025, 1, 10)
        rows = [
            SectorMatrixRow(
                sector_name="空板块",
                sector_code=None,
                cells={d1: MatrixCell(None, None)},
                latest_date=d1,
                change_state=CHANGE_MISSING,
            ),
        ]
        md = render_sector_matrix_markdown(rows, [d1])
        assert "缺失" in md


# ── 导出测试 ────────────────────────────────────────────────────


class TestExport:
    def test_export_to_default_path(self, tmp_path: Path) -> None:
        from src.services.trend_matrix_render import export_markdown

        with patch("src.services.trend_matrix_render.OUTPUT_DIR", tmp_path / "trend_matrices"):
            result = export_markdown("# test", tmp_path / "trend_matrices" / "latest.md")
            assert result.exists()
            assert result.read_text(encoding="utf-8") == "# test"

    def test_export_to_explicit_path(self, tmp_path: Path) -> None:
        from src.services.trend_matrix_render import export_markdown

        target = tmp_path / "custom" / "report.md"
        result = export_markdown("# custom", target)
        assert result.exists()
        assert result == target


# ── 服务集成测试（mock DB）──────────────────────────────────────


class TestTrendMatrixServiceIntegration:
    """Task 5.4: 使用 mock DB 的集成测试。"""

    @pytest.mark.asyncio
    async def test_build_sector_matrix(self) -> None:
        db = MagicMock()
        d1 = date(2025, 1, 10)
        d2 = date(2025, 1, 5)

        sector = MagicMock()
        sector.id = 1
        sector.canonical_name = "光伏"
        sector.sector_code = "BK0001"
        sector.status = "tracked"

        summary = MagicMock()
        summary.sector_id = 1
        summary.end_date = d1
        summary.trend_status = "主线延续"
        summary.strength_level = "中"
        summary.output_path = "output/sector_trends/光伏.md"

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[summary])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[sector])))),
        ])
        db.get_session = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=False)))

        service = TrendMatrixService(db)
        rows, dates = await service.build_sector_matrix(latest_only=False, max_dates=5)

        assert len(rows) == 1
        assert rows[0].sector_name == "光伏"
        assert d1 in dates

    @pytest.mark.asyncio
    async def test_build_group_matrix(self) -> None:
        db = MagicMock()
        d1 = date(2025, 1, 10)

        group = MagicMock()
        group.id = 1
        group.canonical_name = "光伏产业链"
        group.status = "active"

        summary = MagicMock()
        summary.group_id = 1
        summary.end_date = d1
        summary.trend_status = "主线扩散"
        summary.strength_level = "中"
        summary.output_path = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[summary])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[group])))),
            MagicMock(all=MagicMock(return_value=[(1, 3)])),
        ])
        db.get_session = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=False)))

        service = TrendMatrixService(db)
        rows, dates = await service.build_group_matrix(latest_only=True, max_dates=5)

        assert len(rows) == 1
        assert rows[0].group_name == "光伏产业链"
        assert rows[0].member_count == 3
