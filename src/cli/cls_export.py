"""CLS 每日 HTML 导出模块。"""

import html
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("output/cls_exports")

# ---------------------------------------------------------------------------
# 2. Export Query Helpers
# ---------------------------------------------------------------------------


def date_window(target_date: date) -> tuple[int, int]:
    """返回本地日历日的起止时间戳（00:00:00 ~ 23:59:59）。"""
    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.combine(target_date, time(23, 59, 59))
    return int(start_dt.timestamp()), int(end_dt.timestamp())


def build_cls_export_path(target_date: date, export_type: str) -> Path:
    """返回目标导出文件路径。

    Args:
        target_date: 导出日期。
        export_type: all / telegraphs / watch。

    Returns:
        默认输出路径，如 output/cls_exports/2026-05-24.html
    """
    date_str = target_date.isoformat()
    if export_type == "telegraphs":
        filename = f"{date_str}_telegraphs.html"
    elif export_type == "watch":
        filename = f"{date_str}_watch.html"
    else:
        filename = f"{date_str}.html"
    return EXPORT_DIR / filename


async def discover_local_dates(
    db,
    export_type: str,
) -> list[date]:
    """从本地 CLS 表中发现所有有数据的日期（去重、升序）。

    根据 export_type 选择扫描哪些表。
    """
    from sqlalchemy import func, select, text

    dates: set[date] = set()

    async with db.get_session() as session:
        if export_type in ("all", "telegraphs"):
            from src.models.schema import CLSTelegraph

            rows = await session.execute(
                select(func.date(func.datetime(CLSTelegraph.ctime, "unixepoch", "localtime")))
                .distinct()
            )
            for (d,) in rows:
                if d is not None:
                    dates.add(d if isinstance(d, date) else date.fromisoformat(str(d)))

        if export_type in ("all", "watch"):
            from src.models.schema import CLSWatchData

            rows = await session.execute(
                select(func.date(func.datetime(CLSWatchData.ctime, "unixepoch", "localtime")))
                .distinct()
            )
            for (d,) in rows:
                if d is not None:
                    dates.add(d if isinstance(d, date) else date.fromisoformat(str(d)))

    return sorted(dates)


async def query_telegraphs_for_date(db, target_date: date) -> list:
    """查询指定日期的电报数据（最新在前）。"""
    from src.services.cls_telegraph_service import CLSTelegraphService

    service = CLSTelegraphService(db)
    start_ts, end_ts = date_window(target_date)
    return await service.list_telegraphs(start_time=start_ts, end_time=end_ts, limit=5000)


async def query_watch_for_date(db, target_date: date) -> list:
    """查询指定日期的看盘数据（最新在前）。"""
    from src.services.cls_watch_service import CLSWatchService

    service = CLSWatchService(db)
    start_ts, end_ts = date_window(target_date)
    return await service.list_watch_data(start_time=start_ts, end_time=end_ts, limit=5000)


def parse_json_field(raw: str | None) -> list[str]:
    """安全解析 stocks/sectors JSON，解析失败返回空列表。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


# ---------------------------------------------------------------------------
# 3. HTML Rendering
# ---------------------------------------------------------------------------

_CLS_CSS = """\
body{margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;line-height:1.8;color:#333}
.container{max-width:800px;margin:2rem auto;padding:2rem 2.5rem;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.header{margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid #eee}
.header h1{font-size:1.4rem;line-height:1.4;margin:0 0 .5rem}
.header .meta{font-size:.85rem;color:#666}
.overview{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}
.overview-card{flex:1;min-width:120px;padding:.8rem 1rem;background:#f8f9fa;border-radius:6px;text-align:center}
.overview-card .count{font-size:1.5rem;font-weight:bold;color:#333}
.overview-card .label{font-size:.8rem;color:#666}
.section{margin-bottom:2rem}
.section h2{font-size:1.1rem;padding-bottom:.5rem;border-bottom:2px solid #576b95;margin-bottom:1rem;color:#576b95}
.item{margin-bottom:1rem;padding:.8rem 1rem;background:#fafafa;border-radius:4px;border-left:3px solid #ddd}
.item .item-meta{font-size:.8rem;color:#666;margin-bottom:.3rem}
.item .item-meta .time{color:#576b95;margin-right:.8rem}
.badge{display:inline-block;padding:0 .4rem;border-radius:3px;font-size:.75rem;font-weight:bold;color:#fff;margin-right:.4rem;vertical-align:middle}
.badge-a{background:#e74c3c}
.badge-b{background:#f39c12}
.badge-c{background:#95a5a6}
.badge-type{background:#3498db}
.item .item-title{font-size:.95rem;font-weight:bold;margin-bottom:.3rem}
.item .item-content{font-size:.9rem;color:#444;white-space:pre-wrap}
.tags{margin-top:.4rem}
.tag{display:inline-block;padding:0 .5rem;margin:.2rem;background:#e8f4f8;border-radius:3px;font-size:.8rem;color:#2980b9}
.no-data{padding:1rem;color:#999;text-align:center;font-style:italic}
"""


def _escape_text(text: str | None) -> str:
    """转义文本并保留换行为 <br>。"""
    if not text:
        return ""
    return html.escape(text).replace("\n", "<br>")


def _render_telegraph_item(item) -> str:
    """渲染单条电报条目。"""
    publish_time = (
        datetime.fromtimestamp(item.ctime).strftime("%H:%M:%S")
        if item.ctime
        else "未知"
    )
    level = (item.level or "C").upper()
    badge_class = {"A": "badge-a", "B": "badge-b"}.get(level, "badge-c")

    parts = [
        '<div class="item">',
        f'<div class="item-meta">',
        f'<span class="time">{html.escape(publish_time)}</span>',
        f'<span class="badge {badge_class}">{html.escape(level)}级</span>',
        f'</div>',
        f'<div class="item-title">{_escape_text(item.title)}</div>',
    ]
    if item.content:
        parts.append(f'<div class="item-content">{_escape_text(item.content)}</div>')
    parts.append('</div>')
    return "\n".join(parts)


def _render_watch_item(item) -> str:
    """渲染单条看盘条目。"""
    publish_time = (
        datetime.fromtimestamp(item.ctime).strftime("%H:%M:%S")
        if item.ctime
        else "未知"
    )
    data_type = item.data_type or "-"
    stocks = parse_json_field(item.stocks)
    sectors = parse_json_field(item.sectors)

    parts = [
        '<div class="item">',
        '<div class="item-meta">',
        f'<span class="time">{html.escape(publish_time)}</span>',
        f'<span class="badge badge-type">{html.escape(data_type)}</span>',
        '</div>',
        f'<div class="item-title">{_escape_text(item.title)}</div>',
    ]
    if item.content:
        parts.append(f'<div class="item-content">{_escape_text(item.content)}</div>')

    tags_html = ""
    if sectors:
        tag_parts = [f'<span class="tag">{html.escape(s)}</span>' for s in sectors]
        tags_html += f'<div class="tags"><strong>板块:</strong> {"".join(tag_parts)}</div>'
    if stocks:
        tag_parts = [f'<span class="tag">{html.escape(s)}</span>' for s in stocks]
        tags_html += f'<div class="tags"><strong>股票:</strong> {"".join(tag_parts)}</div>'
    if tags_html:
        parts.append(tags_html)

    parts.append('</div>')
    return "\n".join(parts)


def _render_telegraphs_section(telegraphs: list, selected: bool, other_has_data: bool) -> str:
    """渲染电报区域。"""
    if not telegraphs:
        if selected and other_has_data:
            return (
                '<div class="section">'
                '<h2>电报</h2>'
                '<div class="no-data">该日无电报数据</div>'
                '</div>'
            )
        return ""

    items_html = "\n".join(_render_telegraph_item(t) for t in telegraphs)
    return (
        '<div class="section">'
        f'<h2>电报 ({len(telegraphs)} 条)</h2>'
        f'{items_html}'
        '</div>'
    )


def _render_watch_section(watch_items: list, selected: bool, other_has_data: bool) -> str:
    """渲染看盘区域。"""
    if not watch_items:
        if selected and other_has_data:
            return (
                '<div class="section">'
                '<h2>看盘数据</h2>'
                '<div class="no-data">该日无看盘数据</div>'
                '</div>'
            )
        return ""

    items_html = "\n".join(_render_watch_item(w) for w in watch_items)
    return (
        '<div class="section">'
        f'<h2>看盘数据 ({len(watch_items)} 条)</h2>'
        f'{items_html}'
        '</div>'
    )


def build_cls_export_html(
    target_date: date,
    export_type: str,
    telegraphs: list,
    watch_items: list,
    generated_at: str,
) -> str:
    """构建 CLS 每日导出 HTML 文档。

    Args:
        target_date: 导出日期。
        export_type: all / telegraphs / watch。
        telegraphs: 电报数据列表。
        watch_items: 看盘数据列表。
        generated_at: 生成时间戳字符串。

    Returns:
        完整 HTML 字符串。
    """
    date_str = target_date.isoformat()
    title = f"CLS 日报 {date_str}"

    include_telegraphs = export_type in ("all", "telegraphs")
    include_watch = export_type in ("all", "watch")

    # 概览卡片
    overview_parts = []
    if include_telegraphs:
        overview_parts.append(
            f'<div class="overview-card"><div class="count">{len(telegraphs)}</div>'
            f'<div class="label">电报</div></div>'
        )
    if include_watch:
        overview_parts.append(
            f'<div class="overview-card"><div class="count">{len(watch_items)}</div>'
            f'<div class="label">看盘数据</div></div>'
        )
    overview_html = f'<div class="overview">{"".join(overview_parts)}</div>'

    # 数据区域
    other_has_data = bool(telegraphs) or bool(watch_items)
    telegraphs_section = _render_telegraphs_section(telegraphs, include_telegraphs, include_watch and bool(watch_items)) if include_telegraphs else ""
    watch_section = _render_watch_section(watch_items, include_watch, include_telegraphs and bool(telegraphs)) if include_watch else ""

    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_CLS_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="container">\n'
        '<div class="header">\n'
        f"<h1>{html.escape(title)}</h1>\n"
        f'<div class="meta">类型: {html.escape(export_type)} | 生成时间: {html.escape(generated_at)}</div>\n'
        "</div>\n"
        f"{overview_html}\n"
        f"{telegraphs_section}\n"
        f"{watch_section}\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# 5. Incrementality and Output
# ---------------------------------------------------------------------------


@dataclass
class CLSExportResult:
    """单日导出结果。"""

    target_date: date
    export_type: str
    output_path: Path
    telegraph_count: int = 0
    watch_count: int = 0
    exported: bool = False
    skipped: bool = False
    no_data: bool = False


def write_export(
    output_path: Path,
    content: str,
    force: bool,
) -> bool:
    """写入导出文件，增量模式下跳过已存在文件。

    Returns:
        True 如果文件已写入，False 如果跳过。
    """
    if output_path.exists() and not force:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return True
