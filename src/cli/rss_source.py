"""RSS 源命令模块 - source add/remove/list/health/fetch。"""

import click
from rich.panel import Panel
from rich.table import Table

from src.api.providers.rss_provider import redact_url
from src.cli.utils import console, run_async
from src.services.rss_source import RSSSourceService
from src.storage.database import get_db
from src.utils.html_detect import looks_like_html_body


@click.group("source")
def rss_source() -> None:
    """RSS 源管理。"""
    pass


@rss_source.command("add")
@click.argument("name")
@click.argument("feed_url")
@click.option("--type", "source_type", default="aggregate", help="源类型: aggregate/category")
def source_add(name: str, feed_url: str, source_type: str) -> None:
    """添加 RSS 源。

    NAME: 源名称（如 `全部`、`财经`）
    FEED_URL: RSS Feed URL
    """
    async def _add() -> None:
        db = await get_db()
        service = RSSSourceService(db)
        source = await service.add_source(
            source_name=name,
            feed_url=feed_url,
            source_type=source_type,
        )
        console.print(Panel(
            f"[bold]源名称:[/bold] {source.source_name}\n"
            f"[bold]源类型:[/bold] {source.source_type}\n"
            f"[bold]Feed URL:[/bold] {redact_url(source.feed_url)}\n"
            f"[bold]状态:[/bold] {'活跃' if source.status == 1 else '停用'}",
            title="[green]RSS 源添加成功[/green]",
            border_style="green",
        ))

    run_async(_add())


@rss_source.command("remove")
@click.argument("name")
def source_remove(name: str) -> None:
    """删除 RSS 源。"""
    async def _remove() -> None:
        db = await get_db()
        service = RSSSourceService(db)
        success = await service.remove_source(name)
        if success:
            console.print(f"[green]已删除 RSS 源: {name}[/green]")
        else:
            console.print(f"[yellow]RSS 源不存在: {name}[/yellow]")

    run_async(_remove())


@rss_source.command("disable")
@click.argument("name")
def source_disable(name: str) -> None:
    """停用 RSS 源。"""
    async def _disable() -> None:
        db = await get_db()
        service = RSSSourceService(db)
        success = await service.disable_source(name)
        if success:
            console.print(f"[green]已停用 RSS 源: {name}[/green]")
        else:
            console.print(f"[yellow]RSS 源不存在: {name}[/yellow]")

    run_async(_disable())


@rss_source.command("enable")
@click.argument("name")
def source_enable(name: str) -> None:
    """启用 RSS 源。"""
    async def _enable() -> None:
        db = await get_db()
        service = RSSSourceService(db)
        success = await service.enable_source(name)
        if success:
            console.print(f"[green]已启用 RSS 源: {name}[/green]")
        else:
            console.print(f"[yellow]RSS 源不存在: {name}[/yellow]")

    run_async(_enable())


@rss_source.command("list")
@click.option("--all", "show_all", is_flag=True, help="显示所有源（含停用）")
def source_list(show_all: bool) -> None:
    """列出 RSS 源。"""
    async def _list() -> None:
        db = await get_db()
        service = RSSSourceService(db)
        sources = await service.list_sources(active_only=not show_all)

        if not sources:
            console.print("[yellow]暂无 RSS 源[/yellow]")
            return

        table = Table(title="RSS 源列表")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("源名称", style="green")
        table.add_column("类型", style="blue")
        table.add_column("Feed URL", style="dim")
        table.add_column("状态", style="dim")
        table.add_column("文章数", style="magenta", justify="right")

        for source in sources:
            status = "[green]活跃[/green]" if source.status == 1 else "[red]停用[/red]"
            article_count = await service.get_source_article_count(source.id)
            table.add_row(
                str(source.id),
                source.source_name,
                source.source_type,
                redact_url(source.feed_url)[:50],
                status,
                str(article_count),
            )

        console.print(table)

        # 配额检查
        is_warning, active_count, plan_limit = await service.check_quota_warning()
        if plan_limit is not None:
            if is_warning:
                console.print(f"\n[yellow]配额警告: 活跃源 {active_count} 超过计划限制 {plan_limit}[/yellow]")
            else:
                console.print(f"\n[dim]活跃源: {active_count}/{plan_limit}[/dim]")

    run_async(_list())


@rss_source.command("health")
@click.argument("name", required=False)
def source_health(name: str | None) -> None:
    """查看 RSS 源健康状态。"""
    async def _health() -> None:
        from datetime import datetime

        from config.settings import get_settings

        db = await get_db()
        service = RSSSourceService(db)
        settings = get_settings()

        if name:
            source = await service.get_source(name)
            if not source:
                console.print(f"[yellow]RSS 源不存在: {name}[/yellow]")
                return
            sources = [source]
        else:
            sources = await service.list_sources(active_only=False)

        if not sources:
            console.print("[yellow]暂无 RSS 源[/yellow]")
            return

        table = Table(title="RSS 源健康状态")
        table.add_column("源名称", style="green")
        table.add_column("状态", style="dim")
        table.add_column("最近成功", style="yellow")
        table.add_column("最新条目", style="yellow")
        table.add_column("连续失败", style="red", justify="right")
        table.add_column("空响应", style="dim", justify="right")
        table.add_column("过期", style="dim")
        table.add_column("最近错误", style="red")

        for source in sources:
            health = await service.get_health(source.id)
            status = "[green]活跃[/green]" if source.status == 1 else "[red]停用[/red]"

            if health:
                last_success = health.last_success_at.strftime("%Y-%m-%d %H:%M") if health.last_success_at else "-"
                latest_item = health.latest_item_time.strftime("%Y-%m-%d %H:%M") if health.latest_item_time else "-"
                is_stale = await service.is_stale(source.id)
                stale_str = "[red]是[/red]" if is_stale else "[green]否[/green]"
                error = (health.last_error_summary or "")[:40]
            else:
                last_success = "-"
                latest_item = "-"
                stale_str = "-"
                error = "-"

            table.add_row(
                source.source_name,
                status,
                last_success,
                latest_item,
                str(health.consecutive_failures if health else 0),
                str(health.empty_response_count if health else 0),
                stale_str,
                error,
            )

        console.print(table)

    run_async(_health())


@rss_source.command("fetch")
def source_fetch() -> None:
    """从所有活跃 RSS 源抓取文章。"""
    async def _fetch() -> None:
        from src.services.fetcher import FetchProgressEvent, FetcherService
        from src.api.weread import WeReadClient
        from src.services.subscription import SubscriptionService

        db = await get_db()
        client = WeReadClient()
        subscription_service = SubscriptionService(db)
        fetcher_service = FetcherService(client, db, subscription_service)

        console.print("[cyan]开始从 RSS 源抓取文章...[/cyan]")

        def on_progress(event: FetchProgressEvent) -> None:
            if event.type == "subscription_start":
                console.print(f"\n[bold cyan]RSS 源: {event.feed_name}[/bold cyan]")
            elif event.type == "article_fetch":
                console.print(f"  [dim]├─ {event.detail}[/dim]")
            elif event.type == "article_skip":
                console.print(f"  [dim]├─ {event.detail}[/dim]")
            elif event.type == "subscription_done":
                console.print(f"  [green]└─ {event.detail}[/green]")
            elif event.type == "waiting":
                console.print(f"  {event.detail}")

        results = await fetcher_service.fetch_from_rss_sources(on_progress=on_progress)

        if not results:
            console.print("[yellow]无活跃 RSS 源[/yellow]")
            return

        total_new = sum(s.inserted_count for s in results.values())
        total_existing = sum(s.existing_count for s in results.values())
        console.print(f"\n[green]RSS 抓取完成: {total_new} 篇新增, {total_existing} 篇已存在[/green]")

    run_async(_fetch())


@rss_source.command("repair")
@click.option("--dry-run", is_flag=True, help="仅统计，不实际修改")
def source_repair(dry_run: bool) -> None:
    """修复 RSS 文章的 HTML 内容存储问题。

    将历史 RSS 文章中误存到 summary 字段的 HTML 正文迁移到 content 字段。
    仅影响 provider='rss'、content 为空、summary 含 HTML 的记录。
    """
    from sqlalchemy import func as sql_func, select, update as sa_update

    from src.models.schema import Article

    async def _repair() -> None:
        db = await get_db()

        async with db.get_session() as session:
            # 查找受影响的 RSS 文章
            result = await session.execute(
                select(Article).where(
                    Article.provider == "rss",
                    (Article.content == "") | Article.content.is_(None),
                    Article.summary.is_not(None),
                )
            )
            candidates = list(result.scalars().all())

            matched = 0
            for article in candidates:
                if looks_like_html_body(article.summary):
                    matched += 1

        console.print(f"[cyan]RSS 文章修复扫描完成[/cyan]")
        console.print(f"  候选记录: {len(candidates)}")
        console.print(f"  HTML 正文匹配: {matched}")

        if matched == 0:
            console.print("[green]无需修复[/green]")
            return

        if dry_run:
            console.print(f"[yellow]dry-run 模式，跳过实际修改[/yellow]")
            return

        updated = 0
        async with db.get_session() as session:
            result = await session.execute(
                select(Article).where(
                    Article.provider == "rss",
                    (Article.content == "") | Article.content.is_(None),
                    Article.summary.is_not(None),
                )
            )
            articles = list(result.scalars().all())

            for article in articles:
                if looks_like_html_body(article.summary):
                    article.content = article.summary
                    article.summary = None
                    updated += 1

            await session.flush()

        console.print(f"[green]修复完成: {updated}/{matched} 条记录已更新[/green]")

    run_async(_repair())
