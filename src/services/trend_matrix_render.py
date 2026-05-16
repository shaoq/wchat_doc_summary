"""趋势矩阵渲染器 - Rich 表格和 Markdown 输出。"""

from datetime import date
from pathlib import Path

from rich.table import Table

from src.services.trend_matrix_service import (
    CHANGE_COOLING,
    CHANGE_MISSING,
    CHANGE_NEW,
    CHANGE_STEADY,
    CHANGE_WARMING,
    CHANGE_WEAKENING,
    ExpandedGroupMatrix,
    GroupMatrixRow,
    MatrixCell,
    SectorMatrixRow,
)

# ── 变化状态样式 ────────────────────────────────────────────────

_CHANGE_STYLE: dict[str, str] = {
    CHANGE_NEW: "[bold green]{label}[/bold green]",
    CHANGE_WARMING: "[green]{label}[/green]",
    CHANGE_STEADY: "[dim]{label}[/dim]",
    CHANGE_COOLING: "[yellow]{label}[/yellow]",
    CHANGE_WEAKENING: "[red]{label}[/red]",
    CHANGE_MISSING: "[dim]{label}[/dim]",
}


def _style_change(state: str) -> str:
    """Rich 样式化变化状态。"""
    template = _CHANGE_STYLE.get(state, "{label}")
    return template.format(label=state)


def _cell_text(cell: MatrixCell) -> str:
    """格式化单元格文本（Rich）。"""
    if cell.trend_status is None:
        return "[dim]-[/dim]"
    parts = [cell.trend_status]
    if cell.strength_level:
        parts.append(cell.strength_level)
    return " ".join(parts)


def _cell_plain(cell: MatrixCell) -> str:
    """格式化单元格纯文本（Markdown）。"""
    if cell.trend_status is None:
        return "-"
    parts = [cell.trend_status]
    if cell.strength_level:
        parts.append(cell.strength_level)
    return " ".join(parts)


def _date_label(d: date) -> str:
    return d.strftime("%m-%d")


# ── Rich 表格渲染 ───────────────────────────────────────────────


def render_sector_matrix_rich(
    rows: list[SectorMatrixRow],
    dates: list[date],
    *,
    title: str = "板块趋势矩阵",
) -> Table:
    """渲染板块矩阵为 Rich Table。"""
    table = Table(title=title)
    table.add_column("板块", style="cyan", min_width=8)
    table.add_column("变化", min_width=4)

    for d in dates:
        table.add_column(_date_label(d), min_width=10)

    for row in rows:
        cells = [_cell_text(row.cells[d]) for d in dates]
        table.add_row(
            row.sector_name,
            _style_change(row.change_state),
            *cells,
        )

    return table


def render_group_matrix_rich(
    rows: list[GroupMatrixRow],
    dates: list[date],
    *,
    title: str = "分组趋势矩阵",
) -> Table:
    """渲染分组矩阵为 Rich Table。"""
    table = Table(title=title)
    table.add_column("分组", style="cyan", min_width=8)
    table.add_column("成员", justify="right", min_width=4)
    table.add_column("变化", min_width=4)

    for d in dates:
        table.add_column(_date_label(d), min_width=10)

    for row in rows:
        cells = [_cell_text(row.cells[d]) for d in dates]
        table.add_row(
            row.group_name,
            str(row.member_count),
            _style_change(row.change_state),
            *cells,
        )

    return table


def render_expanded_group_rich(
    matrix: ExpandedGroupMatrix,
    dates: list[date],
    *,
    title: str | None = None,
) -> Table:
    """渲染展开分组矩阵为 Rich Table。"""
    group_name = matrix.group_row.group_name
    actual_title = title or f"分组展开: {group_name}"

    table = Table(title=actual_title)
    table.add_column("名称", style="cyan", min_width=8)
    table.add_column("关系", style="dim", min_width=4)
    table.add_column("变化", min_width=4)

    for d in dates:
        table.add_column(_date_label(d), min_width=10)

    # 分组行
    group_cells = [_cell_text(matrix.group_row.cells[d]) for d in dates]
    table.add_row(
        f"[bold]{group_name}[/bold]",
        "[dim]group[/dim]",
        _style_change(matrix.group_row.change_state),
        *group_cells,
    )

    # 成员板块行
    for member_row in matrix.member_rows:
        member_cells = [_cell_text(member_row.cells[d]) for d in dates]
        table.add_row(
            f"  {member_row.sector_name}",
            "",
            _style_change(member_row.change_state),
            *member_cells,
        )

    return table


# ── Markdown 渲染 ───────────────────────────────────────────────


def render_sector_matrix_markdown(
    rows: list[SectorMatrixRow],
    dates: list[date],
    *,
    title: str = "板块趋势矩阵",
) -> str:
    """渲染板块矩阵为 Markdown 表格。"""
    lines: list[str] = [f"# {title}", ""]

    # 表头
    header = "| 板块 | 变化 | " + " | ".join(_date_label(d) for d in dates) + " |"
    sep = "| --- | --- | " + " | ".join("---" for _ in dates) + " |"
    lines.append(header)
    lines.append(sep)

    for row in rows:
        cells = [_cell_plain(row.cells[d]) for d in dates]
        lines.append(
            f"| {row.sector_name} | {row.change_state} | "
            + " | ".join(cells)
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


def render_group_matrix_markdown(
    rows: list[GroupMatrixRow],
    dates: list[date],
    *,
    title: str = "分组趋势矩阵",
) -> str:
    """渲染分组矩阵为 Markdown 表格。"""
    lines: list[str] = [f"# {title}", ""]

    header = "| 分组 | 成员 | 变化 | " + " | ".join(_date_label(d) for d in dates) + " |"
    sep = "| --- | --- | --- | " + " | ".join("---" for _ in dates) + " |"
    lines.append(header)
    lines.append(sep)

    for row in rows:
        cells = [_cell_plain(row.cells[d]) for d in dates]
        lines.append(
            f"| {row.group_name} | {row.member_count} | {row.change_state} | "
            + " | ".join(cells)
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


def render_expanded_group_markdown(
    matrix: ExpandedGroupMatrix,
    dates: list[date],
    *,
    title: str | None = None,
) -> str:
    """渲染展开分组矩阵为 Markdown 表格。"""
    group_name = matrix.group_row.group_name
    actual_title = title or f"分组展开: {group_name}"
    lines: list[str] = [f"# {actual_title}", ""]

    header = "| 名称 | 关系 | 变化 | " + " | ".join(_date_label(d) for d in dates) + " |"
    sep = "| --- | --- | --- | " + " | ".join("---" for _ in dates) + " |"
    lines.append(header)
    lines.append(sep)

    # 分组行
    group_cells = [_cell_plain(matrix.group_row.cells[d]) for d in dates]
    lines.append(
        f"| **{group_name}** | group | {matrix.group_row.change_state} | "
        + " | ".join(group_cells)
        + " |"
    )

    # 成员板块行
    for member_row in matrix.member_rows:
        member_cells = [_cell_plain(member_row.cells[d]) for d in dates]
        lines.append(
            f"| {member_row.sector_name} | | {member_row.change_state} | "
            + " | ".join(member_cells)
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


# ── 导出 ────────────────────────────────────────────────────────

OUTPUT_DIR = Path("output/trend_matrices")


def export_markdown(content: str, path: Path | None = None) -> Path:
    """导出 Markdown 内容到文件。

    Args:
        content: Markdown 文本
        path: 显式输出路径，或 None 使用默认路径

    Returns:
        实际写入的文件路径
    """
    target = path or OUTPUT_DIR / "latest.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
