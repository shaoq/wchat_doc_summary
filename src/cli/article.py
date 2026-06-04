"""文章命令模块 - article, show, export。"""

import html
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from src.cli.utils import console, run_async
from src.utils.html_detect import looks_like_html_body
from src.models.schema import Article, Feed
from src.services.subscription import SubscriptionService
from src.storage.database import get_db

logger = logging.getLogger(__name__)

# 导出相关常量
EXPORT_BASE_DIR = Path("output/export_articles")
UNSAFE_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]')
TITLE_MAX_LENGTH = 30


@dataclass
class ExportSummary:
    """单次导出的汇总结果。"""

    feed_name: str
    mp_id: str
    output_dir: Path
    exported: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0


@click.command()
@click.argument('article_id', type=int)
def article(article_id: int) -> None:
    """查看文章详情。

    ARTICLE_ID: 文章 ID
    """
    async def _article() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            article_obj = result.scalar_one_or_none()

        if not article_obj:
            console.print(f"[red]文章不存在: {article_id}[/red]")
            return

        console.print(Panel(
            f"[bold]标题:[/bold] {article_obj.title}\n"
            f"[bold]文章 ID:[/bold] {article_obj.article_id}\n"
            f"[bold]发布时间:[/bold] {article_obj.publish_time.strftime('%Y-%m-%d %H:%M') if article_obj.publish_time else '未知'}\n"
            f"[bold]原文链接:[/bold] {article_obj.original_url or '无'}\n"
            f"[bold]摘要:[/bold] {article_obj.summary or '未生成'}\n"
            f"[bold]内容长度:[/bold] {len(article_obj.content) if article_obj.content else 0} 字符",
            title="[cyan]文章详情[/cyan]",
            border_style="cyan",
        ))

    run_async(_article())


@click.command()
@click.argument('mp_id')
@click.option('--limit', '-n', type=int, default=20, help='显示数量')
@click.option('--offset', '-o', type=int, default=0, help='偏移量')
@click.option('--all', '-a', 'show_all', is_flag=True, help='显示全部')
def show(mp_id: str, limit: int, offset: int, show_all: bool) -> None:
    """查看公众号已抓取的文章列表。

    MP_ID: 公众号 ID
    """
    async def _show() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        # 验证订阅存在
        feed = await subscription_service.get_subscription(mp_id)
        if not feed:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        from sqlalchemy import func as sql_func, select

        async with db.get_session() as session:
            # 获取总数
            count_result = await session.execute(
                select(sql_func.count(Article.id)).where(Article.feed_id == feed.id)
            )
            total = count_result.scalar() or 0

            if total == 0:
                console.print(f"[yellow]该公众号暂无已抓取的文章[/yellow]")
                return

            # 查询文章列表
            query = (
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
            )
            if not show_all:
                query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            articles = result.scalars().all()

        # 显示表格
        table = Table(title=f"{feed.name} - 文章列表 (共 {total} 篇)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("标题", style="green", max_width=40)
        table.add_column("原文链接", style="blue", max_width=50, no_wrap=True)
        table.add_column("发布时间", style="dim")

        for article in articles:
            title_display = article.title[:37] + "..." if len(article.title) > 40 else article.title
            url_display = article.original_url or "无"
            pub_time = article.publish_time.strftime("%Y-%m-%d %H:%M") if article.publish_time else "未知"
            table.add_row(str(article.id), title_display, url_display, pub_time)

        console.print(table)

        # 分页提示
        if not show_all and total > limit:
            current_end = offset + len(articles)
            console.print(f"\n[dim]显示 {offset + 1}-{current_end}/{total}，使用 --offset {offset + limit} 查看更多[/dim]")

        console.print("[dim]使用 wchat article <ID> 查看完整原文链接[/dim]")

    run_async(_show())


def sanitize_filename(title: str, max_length: int = TITLE_MAX_LENGTH) -> str:
    """替换文件系统不安全字符为 `_`，截断标题至指定长度。"""
    safe = UNSAFE_FILENAME_CHARS.sub('_', title)
    return safe[:max_length]


def build_export_dir(mp_id: str) -> Path:
    """返回导出目录路径 output/export_articles/<mp_id>/。"""
    return EXPORT_BASE_DIR / mp_id


def build_export_filename(export_dir: Path, date_prefix: str, title: str) -> str:
    """组合日期前缀 + 截断标题生成文件名，处理重名。"""
    safe_title = sanitize_filename(title)
    base_name = f"{date_prefix}_{safe_name}" if (safe_name := safe_title) else date_prefix
    filename = f"{base_name}.html"

    # 处理重名：追加序号
    if export_dir.exists() and (export_dir / filename).exists():
        seq = 2
        while (export_dir / f"{base_name}_{seq}.html").exists():
            seq += 1
        filename = f"{base_name}_{seq}.html"

    return filename


_ARTICLE_CSS = """\
body{margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;line-height:1.8;color:#333}
.article{max-width:720px;margin:2rem auto;padding:2rem 2.5rem;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.article-header{margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid #eee}
.article-header h1{font-size:1.5rem;line-height:1.4;margin:0 0 .8rem}
.article-meta{font-size:.85rem;color:#666}
.article-meta span{margin-right:1.2rem}
.article-meta a{color:#576b95;text-decoration:none}
.article-summary{margin:1rem 0;padding:.8rem 1rem;background:#f8f9fa;border-left:3px solid #576b95;font-size:.9rem;color:#555;border-radius:0 4px 4px 0}
.article-content img{max-width:100%;height:auto}
.article-content{word-break:break-word}"""


def build_article_html(article_obj: Article) -> str:
    """生成单篇文章的完整 HTML 文档。"""
    title = html.escape(article_obj.title or "")

    # 元信息行
    meta_parts: list[str] = []
    if article_obj.publish_time:
        meta_parts.append(
            f'<span>发布时间: {html.escape(article_obj.publish_time.strftime("%Y-%m-%d %H:%M"))}</span>'
        )
    if article_obj.original_url:
        meta_parts.append(
            f'<span>原文链接: <a href="{html.escape(article_obj.original_url)}" target="_blank">查看原文</a></span>'
        )
    if article_obj.pic_url:
        meta_parts.append(
            f'<span>封面图片: <img src="{html.escape(article_obj.pic_url)}" alt="封面" style="max-width:200px;vertical-align:middle"></span>'
        )
    meta_html = "\n".join(meta_parts)

    # 历史 RSS 回退：content 为空但 summary 含 HTML body 时，将 summary 用作正文
    summary_used_as_body = False
    body_html = article_obj.content or ""
    if not body_html and article_obj.provider == "rss" and looks_like_html_body(article_obj.summary):
        body_html = article_obj.summary or ""
        summary_used_as_body = True

    # 摘要：仅当 summary 未被用作正文回退时才显示
    summary_html = ""
    if article_obj.summary and not summary_used_as_body:
        summary_html = f'<div class="article-summary">{html.escape(article_obj.summary)}</div>'

    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>{_ARTICLE_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<main class="article">\n'
        '<header class="article-header">\n'
        f"<h1>{title}</h1>\n"
        f'<div class="article-meta">\n{meta_html}\n</div>\n'
        f"{summary_html}\n"
        "</header>\n"
        f'<article class="article-content">\n{body_html}\n</article>\n'
        "</main>\n"
        "</body>\n"
        "</html>"
    )


def _export_feed_articles(
    feed: Feed,
    articles: list[Article],
    force: bool,
) -> ExportSummary:
    """导出单个公众号的文章，返回汇总结果。

    Args:
        feed: 公众号 Feed 对象。
        articles: 待导出的文章列表。
        force: 是否强制全量覆盖。

    Returns:
        ExportSummary 汇总结果。
    """
    summary = ExportSummary(
        feed_name=feed.name,
        mp_id=feed.mp_id,
        output_dir=build_export_dir(feed.mp_id),
        total=len(articles),
    )

    if not articles:
        return summary

    # 准备导出目录
    if force and summary.output_dir.exists():
        shutil.rmtree(summary.output_dir)
    summary.output_dir.mkdir(parents=True, exist_ok=True)

    for article_obj in articles:
        # 日期前缀
        if article_obj.publish_time:
            date_prefix = article_obj.publish_time.strftime('%Y-%m-%d')
        else:
            date_prefix = 'unknown-date'

        # 先生成基础文件名用于增量跳过检查
        safe_title = sanitize_filename(article_obj.title)
        base_name = f"{date_prefix}_{safe_title}" if safe_title else date_prefix
        base_filename = f"{base_name}.html"

        # 增量模式：跳过已存在文件
        if not force and (summary.output_dir / base_filename).exists():
            summary.skipped += 1
            continue

        # 实际写入时使用完整文件名（含重名处理）
        filename = build_export_filename(summary.output_dir, date_prefix, article_obj.title)
        file_path = summary.output_dir / filename

        try:
            content = build_article_html(article_obj)
            file_path.write_text(content, encoding='utf-8')
            summary.exported += 1
        except Exception:
            logger.warning(
                "导出文章失败: id=%d title=%s",
                article_obj.id,
                article_obj.title,
                exc_info=True,
            )
            summary.failed += 1

    return summary


def _print_summary_line(summary: ExportSummary) -> None:
    """打印单条导出汇总行。"""
    parts = [
        f"新导出: {summary.exported}",
        f"已存在跳过: {summary.skipped}",
    ]
    failed_part = f"失败: [red]{summary.failed}[/red]" if summary.failed else f"失败: {summary.failed}"
    parts.append(failed_part)
    parts.append(f"总计: {summary.total}")

    console.print(f"  {('，').join(parts)}")


@click.command()
@click.argument('args', nargs=-1)
@click.option('--force', is_flag=True, help='强制全量导出，覆盖已存在文件')
@click.option('--all', 'export_all', is_flag=True, help='导出所有订阅的公众号')
def export(args: tuple[str, ...], force: bool, export_all: bool) -> None:
    """导出公众号文章为 HTML 文件。

    MP_ID: 公众号 ID（与 --all 二选一）

    文章将导出到 output/export_articles/<MP_ID>/ 目录下，
    每篇文章一个独立的 .html 文件。默认增量导出，使用 --force 全量覆盖。

    设置是否参与批量导出:
    wchat export set-export <MP_ID> true|false
    """
    if args and args[0] == "set-export":
        _set_export_preference(args, force, export_all)
        return

    if len(args) > 1:
        console.print("[red]只能指定一个公众号 ID[/red]")
        console.print("[dim]用法: wchat export <MP_ID>  或  wchat export --all[/dim]")
        return

    mp_id = args[0] if args else None

    # 校验参数
    if mp_id is None and not export_all:
        console.print("[red]请指定公众号 ID 或使用 --all 导出所有订阅[/red]")
        console.print("[dim]用法: wchat export <MP_ID>  或  wchat export --all[/dim]")
        return

    if mp_id is not None and export_all:
        console.print("[red]不能同时指定公众号 ID 和 --all[/red]")
        console.print("[dim]用法: wchat export <MP_ID>  或  wchat export --all[/dim]")
        return

    mode_label = "强制重建" if force else "增量"

    if export_all:
        _export_all(force, mode_label)
    else:
        assert mp_id is not None
        _export_single(mp_id, force, mode_label)


def _set_export_preference(args: tuple[str, ...], force: bool, export_all: bool) -> None:
    """设置公众号是否参与 export --all。"""
    if force or export_all:
        console.print("[red]set-export 不支持 --force 或 --all[/red]")
        console.print("[dim]用法: wchat export set-export <MP_ID> true|false[/dim]")
        return

    if len(args) != 3:
        console.print("[red]请指定公众号 ID 和 true|false[/red]")
        console.print("[dim]用法: wchat export set-export <MP_ID> true|false[/dim]")
        return

    _, mp_id, raw_enabled = args
    normalized = raw_enabled.lower()
    if normalized not in {"true", "false"}:
        console.print("[red]导出标识必须是 true 或 false[/red]")
        console.print("[dim]用法: wchat export set-export <MP_ID> true|false[/dim]")
        return

    enabled = normalized == "true"

    async def _do_set_export_preference() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)
        feed = await subscription_service.set_export_all_preference(mp_id, enabled)
        if feed is None:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        state = "参与" if enabled else "不参与"
        console.print(f"[green]已设置 {feed.name} ({feed.mp_id}) {state}批量导出[/green]")

    run_async(_do_set_export_preference())


def _export_single(mp_id: str, force: bool, mode_label: str) -> None:
    """导出单个公众号文章。"""
    async def _do_export() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            feed_result = await session.execute(
                select(Feed).where(Feed.mp_id == mp_id)
            )
            feed = feed_result.scalar_one_or_none()
            if feed is None:
                console.print(f"[red]订阅不存在: {mp_id}[/red]")
                return

            query = (
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            articles = list(result.scalars().all())

        export_dir = build_export_dir(mp_id)

        # 单账号开始输出
        console.print(f"[bold]{feed.name}[/bold] ({mp_id})")
        console.print(f"  模式: {mode_label}")
        console.print(f"  格式: HTML")
        console.print(f"  输出目录: {export_dir}")

        summary = _export_feed_articles(feed, articles, force)

        if summary.total == 0:
            console.print("[yellow]  没有可导出的文章[/yellow]")
            return

        if summary.exported == 0 and summary.skipped > 0:
            console.print("[yellow]  没有新文章需要导出，所有文章均已存在[/yellow]")

        _print_summary_line(summary)

    run_async(_do_export())


def _export_all(force: bool, mode_label: str) -> None:
    """导出所有活跃订阅的文章。"""
    async def _do_export_all() -> None:
        from sqlalchemy import select

        db = await get_db()

        async with db.get_session() as session:
            active_count_result = await session.execute(
                select(Feed).where(Feed.status == 1)
            )
            active_feeds = list(active_count_result.scalars().all())

            feeds_result = await session.execute(
                select(Feed)
                .where(Feed.status == 1, Feed.include_in_export_all == 1)
                .order_by(Feed.name, Feed.mp_id)
            )
            feeds = list(feeds_result.scalars().all())

        if not feeds:
            if active_feeds:
                console.print("[yellow]没有启用批量导出的订阅[/yellow]")
                console.print("[dim]可使用 wchat export set-export <MP_ID> true 启用[/dim]")
            else:
                console.print("[yellow]没有活跃的订阅[/yellow]")
            return

        total_feeds = len(feeds)

        # 批量开始输出
        console.print(f"批量导出: {total_feeds} 个公众号")
        console.print(f"模式: {mode_label}")
        console.print(f"格式: HTML")
        console.print("")

        # 聚合统计
        agg_exported = 0
        agg_skipped = 0
        agg_failed = 0
        agg_total = 0
        agg_feeds_done = 0

        from sqlalchemy import select as sa_select

        db = await get_db()

        for idx, feed in enumerate(feeds, start=1):
            async with db.get_session() as session:
                articles_result = await session.execute(
                    sa_select(Article)
                    .where(Article.feed_id == feed.id)
                    .order_by(Article.publish_time.desc())
                )
                articles = list(articles_result.scalars().all())

            console.print(f"[{idx}/{total_feeds}] [bold]{feed.name}[/bold] ({feed.mp_id})")

            summary = _export_feed_articles(feed, articles, force)

            if summary.total == 0:
                console.print("[yellow]  没有可导出的文章[/yellow]")
            elif summary.exported == 0 and summary.skipped > 0:
                console.print("[yellow]  没有新文章需要导出[/yellow]")

            if summary.total > 0:
                console.print(f"  输出目录: {summary.output_dir}")
                _print_summary_line(summary)

            agg_exported += summary.exported
            agg_skipped += summary.skipped
            agg_failed += summary.failed
            agg_total += summary.total
            agg_feeds_done += 1

        # 聚合汇总
        console.print("")
        console.print("[bold]总计[/bold]")
        console.print(f"  公众号: {agg_feeds_done}")
        console.print(f"  新导出: {agg_exported}")
        console.print(f"  已存在跳过: {agg_skipped}")
        agg_failed_line = f"  失败: [red]{agg_failed}[/red]" if agg_failed else f"  失败: {agg_failed}"
        console.print(agg_failed_line)
        console.print(f"  文章总数: {agg_total}")

    run_async(_do_export_all())
