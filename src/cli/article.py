"""文章命令模块 - article, show, export。"""

import json
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from src.cli.utils import console, run_async
from src.models.schema import Article, Feed
from src.services.subscription import SubscriptionService
from src.storage.database import get_db


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
        table.add_column("原文链接", style="blue", max_width=35)
        table.add_column("发布时间", style="dim")

        for article in articles:
            title_display = article.title[:37] + "..." if len(article.title) > 40 else article.title
            url_display = (article.original_url or "无")[:32] + "..." if article.original_url and len(article.original_url) > 35 else (article.original_url or "无")
            pub_time = article.publish_time.strftime("%Y-%m-%d %H:%M") if article.publish_time else "未知"
            table.add_row(str(article.id), title_display, url_display, pub_time)

        console.print(table)

        # 分页提示
        if not show_all and total > limit:
            current_end = offset + len(articles)
            console.print(f"\n[dim]显示 {offset + 1}-{current_end}/{total}，使用 --offset {offset + limit} 查看更多[/dim]")

    run_async(_show())


@click.command()
@click.option('--format', 'output_format', type=click.Choice(['json', 'markdown']), default='json', help='输出格式')
@click.option('--output', '-o', type=click.Path(), default='articles.json', help='输出文件路径')
@click.option('--mp-id', 'mp_id', help='指定公众号 ID（可选）')
def export(output_format: str, output: str, mp_id: str | None) -> None:
    """导出文章。"""
    async def _export() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            query = select(Article).join(Feed)

            if mp_id:
                query = query.where(Feed.mp_id == mp_id)

            query = query.order_by(Article.publish_time.desc())
            result = await session.execute(query)
            articles = list(result.scalars().all())

        if not articles:
            console.print("[yellow]没有可导出的文章[/yellow]")
            return

        output_path = Path(output)

        if output_format == 'json':
            data = []
            for article in articles:
                data.append({
                    "id": article.id,
                    "article_id": article.article_id,
                    "title": article.title,
                    "content": article.content,
                    "summary": article.summary,
                    "pic_url": article.pic_url,
                    "original_url": article.original_url,
                    "publish_time": article.publish_time.isoformat() if article.publish_time else None,
                    "created_at": article.created_at.isoformat() if article.created_at else None,
                })

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        else:  # markdown
            lines = ["# 文章导出\n\n"]

            for article in articles:
                lines.append(f"## {article.title}\n\n")
                if article.summary:
                    lines.append(f"**摘要**: {article.summary}\n\n")
                if article.publish_time:
                    lines.append(f"**发布时间**: {article.publish_time.strftime('%Y-%m-%d %H:%M')}\n\n")
                if article.original_url:
                    lines.append(f"**原文链接**: {article.original_url}\n\n")
                if article.content:
                    lines.append(f"### 正文\n\n{article.content}\n\n")
                lines.append("---\n\n")

            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

        console.print(f"[green]导出成功: {output_path}[/green]")
        console.print(f"  文章数量: {len(articles)}")

    run_async(_export())
