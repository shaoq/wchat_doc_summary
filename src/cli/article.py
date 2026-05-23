"""文章命令模块 - article, show, export。"""

import html
import re
import shutil
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from src.cli.utils import console, run_async
from src.models.schema import Article, Feed
from src.services.subscription import SubscriptionService
from src.storage.database import get_db

# 导出相关常量
EXPORT_BASE_DIR = Path("output/export_articles")
UNSAFE_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]')
TITLE_MAX_LENGTH = 30


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

    # 摘要
    summary_html = ""
    if article_obj.summary:
        summary_html = f'<div class="article-summary">{html.escape(article_obj.summary)}</div>'

    # 正文：保留存储的 HTML，不调用 html_to_markdown
    body_html = article_obj.content or ""

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


@click.command()
@click.argument('mp_id')
@click.option('--force', is_flag=True, help='强制全量导出，覆盖已存在文件')
def export(mp_id: str, force: bool) -> None:
    """导出公众号文章为 HTML 文件。

    MP_ID: 公众号 ID

    文章将导出到 output/export_articles/<MP_ID>/ 目录下，
    每篇文章一个独立的 .html 文件。默认增量导出，使用 --force 全量覆盖。
    """
    async def _export() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            # 验证公众号存在
            feed_result = await session.execute(
                select(Feed.id).where(Feed.mp_id == mp_id)
            )
            feed_id = feed_result.scalar_one_or_none()
            if feed_id is None:
                console.print(f"[red]订阅不存在: {mp_id}[/red]")
                return

            # 查询所有文章
            query = (
                select(Article)
                .where(Article.feed_id == feed_id)
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            articles = list(result.scalars().all())

        if not articles:
            console.print("[yellow]没有可导出的文章[/yellow]")
            return

        # 准备导出目录
        export_dir = build_export_dir(mp_id)
        if force and export_dir.exists():
            shutil.rmtree(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        # 逐篇导出
        exported = 0
        skipped = 0

        for article_obj in articles:
            # 日期前缀
            if article_obj.publish_time:
                date_prefix = article_obj.publish_time.strftime('%Y-%m-%d')
            else:
                date_prefix = 'unknown-date'

            filename = build_export_filename(export_dir, date_prefix, article_obj.title)
            file_path = export_dir / filename

            # 增量模式：跳过已存在文件
            if not force and file_path.exists():
                skipped += 1
                continue

            content = build_article_html(article_obj)
            file_path.write_text(content, encoding='utf-8')
            exported += 1

        # 汇总输出
        console.print(f"[green]导出完成: {export_dir}[/green]")
        console.print(f"  导出: [cyan]{exported}[/cyan] 篇，跳过: [dim]{skipped}[/dim] 篇，共 [bold]{len(articles)}[/bold] 篇")

    run_async(_export())
