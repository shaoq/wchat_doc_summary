"""订阅命令模块 - subscribe, unsubscribe, ls, info, fetch。"""

import click
from rich.panel import Panel
from rich.table import Table

from config.settings import get_settings
from src.api.weread import AuthExpiredError, RateLimitError, WeReadClient
from src.cli.utils import console, run_async
from src.models.schema import Article, Feed
from src.services.auth import AuthService
from src.services.fetcher import DEFAULT_LATEST_COUNT, FetchFinalState, FetchProgressEvent, FetchSummary, FetcherService
from src.services.rss_source import RSSSourceService
from src.services.subscription import SubscriptionService
from src.services.trade_calendar import get_effective_fetch_trade_date
from src.storage.database import get_db


def _provider_requires_weread_auth(provider_name: str) -> bool:
    """判断指定 Provider 是否依赖 WeRead 登录。"""
    return provider_name == "weread"


def _print_fetch_summary(mp_id: str, summary: FetchSummary) -> None:
    """格式化输出单个订阅的抓取摘要。"""
    if summary.final_state == FetchFinalState.SUSPICIOUS_EMPTY:
        console.print(f"  {mp_id}: [yellow]可疑空结果（重试后仍为空）[/yellow]")
        return
    if summary.final_state == FetchFinalState.ERROR:
        console.print(f"  {mp_id}: [red]抓取失败[/red]")
        return
    if summary.final_state == FetchFinalState.EMPTY_RESULT:
        console.print(f"  {mp_id}: [dim]上游返回空结果[/dim]")
        return
    if summary.final_state == FetchFinalState.NO_NEW:
        console.print(f"  {mp_id}: [dim]无新增（已存在 {summary.existing_count} 篇）[/dim]")
        return
    # SUCCESS
    parts = [f"{summary.inserted_count} 篇新增"]
    if summary.existing_count:
        parts.append(f"{summary.existing_count} 篇已存在")
    if summary.failed_count:
        parts.append(f"[red]{summary.failed_count} 篇失败[/red]")
    console.print(f"  {mp_id}: [green]{', '.join(parts)}[/green]")


def _resolve_feed_provider(mp_id: str, provider_name: str | None, default_provider: str) -> str:
    """兼容历史订阅的 Provider 推断。"""
    if provider_name:
        return provider_name
    if mp_id.startswith("MP_WXS_"):
        return "weread"
    return default_provider


@click.command()
@click.argument('url')
def subscribe(url: str) -> None:
    """订阅公众号（通过文章 URL）。

    URL: 微信公众号文章链接
    """
    async def _subscribe() -> None:
        db = await get_db()
        client = WeReadClient()
        auth_service = AuthService(client, db)
        subscription_service = SubscriptionService(db)
        fetcher_service = FetcherService(client, db, subscription_service)
        provider_name = get_settings().article_list_provider

        if _provider_requires_weread_auth(provider_name):
            token = await auth_service.get_current_token()
            if not token:
                console.print("[red]请先登录: wchat login[/red]")
                return

        with console.status("[bold blue]获取公众号信息...[/bold blue]"):
            try:
                mp_info = await fetcher_service.get_mp_info_from_article(url)
            except Exception as e:
                console.print(f"[red]获取公众号信息失败: {e}[/red]")
                return

        mp_id = mp_info.get("mp_id")
        name = mp_info.get("name")
        intro = mp_info.get("intro", "")
        cover = mp_info.get("cover", "")

        if not mp_id or not name:
            console.print("[red]无法获取公众号信息[/red]")
            return

        # 添加订阅
        feed, _ = await subscription_service.add_subscription(
            mp_id=mp_id,
            name=name,
            intro=intro,
            cover=cover,
            provider=mp_info.get("provider"),
            provider_feed_id=mp_info.get("provider_feed_id"),
            provider_meta=mp_info.get("provider_meta"),
        )

        console.print(Panel(
            f"[bold]公众号名称:[/bold] {name}\n"
            f"[bold]公众号 ID:[/bold] {mp_id}\n"
            f"[bold]简介:[/bold] {intro[:100] + '...' if len(intro) > 100 else intro}",
            title="[green]订阅成功[/green]",
            border_style="green",
        ))

    run_async(_subscribe())


@click.command()
@click.argument('mp_id')
def unsubscribe(mp_id: str) -> None:
    """取消订阅。

    MP_ID: 公众号 ID
    """
    async def _unsubscribe() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        success = await subscription_service.remove_subscription(mp_id)

        if success:
            console.print(f"[green]已取消订阅: {mp_id}[/green]")
        else:
            console.print(f"[yellow]订阅不存在: {mp_id}[/yellow]")

    run_async(_unsubscribe())


@click.command()
@click.option('--active-only', is_flag=True, default=True, help='只显示活跃订阅')
def ls(active_only: bool) -> None:
    """查看订阅列表。"""
    async def _ls() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)
        rss_service = RSSSourceService(db)

        # 使用新方法获取订阅及统计数据
        feeds_with_stats = await subscription_service.list_subscriptions_with_stats(active_only=active_only)

        if not feeds_with_stats:
            console.print("[yellow]暂无订阅[/yellow]")
            return

        table = Table(title="订阅列表")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("公众号名称", style="green")
        table.add_column("公众号 ID", style="blue")
        table.add_column("权重", style="magenta", justify="center")
        table.add_column("文章数", style="magenta", justify="right")
        table.add_column("最近文章", style="yellow")
        table.add_column("RSS 源", style="dim")
        table.add_column("状态", style="dim")
        table.add_column("最后同步", style="dim")

        for feed, article_count, latest_article_time in feeds_with_stats:
            status = "[green]活跃[/green]" if feed.status == 1 else "[red]停用[/red]"
            sync_time = feed.sync_time.strftime("%Y-%m-%d %H:%M") if feed.sync_time else "从未同步"
            latest_time = latest_article_time.strftime("%Y-%m-%d") if latest_article_time else "-"
            weight_labels = {0: "[dim]低[/dim]", 5: "[yellow]中[/yellow]", 10: "[bold red]高[/bold red]"}
            weight_display = weight_labels.get(feed.weight, str(feed.weight))

            # 查找关联的 RSS 源
            from sqlalchemy import select, func
            from src.models.schema import RSSArticleMembership, RSSSource
            rss_sources: list[str] = []
            async with db.get_session() as session:
                result = await session.execute(
                    select(RSSSource.source_name)
                    .join(RSSArticleMembership, RSSArticleMembership.source_id == RSSSource.id)
                    .join(Article, Article.id == RSSArticleMembership.article_id)
                    .where(Article.feed_id == feed.id)
                    .group_by(RSSSource.source_name)
                    .limit(3)
                )
                rss_sources = [row[0] for row in result.all()]
            rss_label = ", ".join(rss_sources) if rss_sources else "-"

            table.add_row(
                str(feed.id),
                feed.name[:20] + "..." if len(feed.name) > 20 else feed.name,
                feed.mp_id[:25] + "..." if len(feed.mp_id) > 25 else feed.mp_id,
                weight_display,
                str(article_count),
                latest_time,
                rss_label,
                status,
                sync_time,
            )

        console.print(table)

    run_async(_ls())


@click.command()
@click.argument('mp_id')
def info(mp_id: str) -> None:
    """查看公众号详细信息。

    MP_ID: 公众号 ID
    """
    async def _info() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        feed = await subscription_service.get_subscription(mp_id)

        if not feed:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        from sqlalchemy import func, select

        from src.models.schema import Article

        # 获取文章统计
        async with db.get_session() as session:
            count_result = await session.execute(
                select(func.count(Article.id)).where(Article.feed_id == feed.id)
            )
            article_count = count_result.scalar() or 0

            latest_result = await session.execute(
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
                .limit(5)
            )
            latest_articles = list(latest_result.scalars().all())

        console.print(Panel(
            f"[bold]名称:[/bold] {feed.name}\n"
            f"[bold]公众号 ID:[/bold] {feed.mp_id}\n"
            f"[bold]简介:[/bold] {feed.intro or '无'}\n"
            f"[bold]状态:[/bold] {'活跃' if feed.status == 1 else '停用'}\n"
            f"[bold]权重:[/bold] {feed.weight} ({'低' if feed.weight == 0 else '中' if feed.weight == 5 else '高'})\n"
            f"[bold]文章数量:[/bold] {article_count}\n"
            f"[bold]创建时间:[/bold] {feed.created_at.strftime('%Y-%m-%d %H:%M') if feed.created_at else '未知'}\n"
            f"[bold]最后同步:[/bold] {feed.sync_time.strftime('%Y-%m-%d %H:%M') if feed.sync_time else '从未同步'}",
            title="[cyan]公众号信息[/cyan]",
            border_style="cyan",
        ))

        if latest_articles:
            console.print("\n[bold]最新文章:[/bold]")
            for article in latest_articles:
                pub_time = article.publish_time.strftime("%Y-%m-%d") if article.publish_time else "未知时间"
                console.print(f"  - [{pub_time}] {article.title[:50]}...")

    run_async(_info())


@click.command()
@click.option('--all', 'fetch_all', is_flag=True, help='抓取所有订阅')
@click.option('--days', 'days', type=int, default=None, help='抓取最近 N 天的文章')
@click.option('--full', 'full', is_flag=True, help='抓取全部历史文章')
@click.option('--force', 'force', is_flag=True, help='强制全新开始（忽略当日进度）')
@click.argument('mp_id', required=False)
def fetch(fetch_all: bool, days: int | None, full: bool, force: bool, mp_id: str | None) -> None:
    """拉取文章。

    MP_ID: 公众号 ID（可选）

    有 RSS 源时默认从 RSS 源抓取；无 RSS 源时需指定公众号或使用 --all。
    """
    # full 参数优先级高于 days
    if full:
        days = None

    async def _fetch() -> None:
        db = await get_db()
        client = WeReadClient()
        auth_service = AuthService(client, db)
        subscription_service = SubscriptionService(db)
        fetcher_service = FetcherService(client, db, subscription_service)
        rss_service = RSSSourceService(db)
        provider_name = get_settings().article_list_provider

        # 检查是否有活跃 RSS 源
        active_sources = await rss_service.list_sources(active_only=True)
        has_rss_sources = len(active_sources) > 0

        # ── RSS 模式：mp_id 被拒绝 ──
        if mp_id and has_rss_sources:
            console.print("[yellow]RSS 模式下不支持按公众号抓取。[/yellow]")
            console.print("[dim]请使用 wchat fetch 进行统一 RSS 抓取[/dim]")
            return

        # ── RSS 模式：wchat fetch 或 wchat fetch --all ──
        if has_rss_sources and not mp_id:
            # RSS 归属服务可能使用 weread 解析公众号身份，需要加载 token
            if _provider_requires_weread_auth(get_settings().rss_identity_resolver_provider):
                token = await auth_service.get_current_token()
                if not token:
                    console.print("[red]请先登录: wchat login[/red]")
                    return

            console.print(f"[cyan]RSS 模式: 从 {len(active_sources)} 个活跃源抓取[/cyan]")

            def on_rss_progress(event: FetchProgressEvent) -> None:
                if event.type == "subscription_start":
                    console.print(f"\n[bold cyan]{event.detail}[/bold cyan] {event.feed_name}")
                elif event.type == "page_fetch":
                    console.print(f"  [dim]├─ {event.detail}[/dim]")
                elif event.type == "article_fetch":
                    console.print(f"  [dim]├─ {event.detail}[/dim]")
                elif event.type == "article_skip":
                    console.print(f"  [dim]├─ {event.detail}[/dim]")
                elif event.type == "waiting":
                    console.print(f"  {event.detail}")
                elif event.type == "rate_limited":
                    console.print(f"  [yellow]{event.detail}[/yellow]")
                elif event.type == "subscription_done":
                    console.print(f"  [green]└─ {event.detail}[/green]")

            results = await fetcher_service.fetch_from_rss_sources(
                on_progress=on_rss_progress,
            )

            if not results:
                console.print("[dim]无抓取结果[/dim]")
            else:
                for source_name, summary in results.items():
                    _print_fetch_summary(source_name, summary)

            return

        # ── 传统模式（无 RSS 源）──
        requires_auth = False
        if fetch_all:
            feeds = await subscription_service.list_subscriptions(active_only=True)
            requires_auth = any(
                _provider_requires_weread_auth(
                    _resolve_feed_provider(feed.mp_id, feed.provider, provider_name)
                )
                for feed in feeds
            )
        elif mp_id:
            feed = await subscription_service.get_subscription(mp_id)
            requires_auth = _provider_requires_weread_auth(
                _resolve_feed_provider(
                    mp_id,
                    feed.provider if feed else None,
                    provider_name,
                )
            )

        if requires_auth:
            token = await auth_service.get_current_token()
            if not token:
                console.print("[red]请先登录: wchat login[/red]")
                return

        # 显示抓取范围
        latest_count = None
        if full:
            console.print("[cyan]抓取范围: 全部历史[/cyan]")
        elif days is not None:
            console.print(f"[cyan]抓取范围: 最近 {days} 天[/cyan]")
        elif fetch_all:
            console.print("[cyan]抓取范围: 批量增量同步[/cyan]")
        else:
            latest_count = DEFAULT_LATEST_COUNT
            console.print(f"[cyan]抓取范围: 最新 {latest_count} 条[/cyan]")

        if fetch_all:
            # 抓取所有订阅（支持 batch 断点续传）
            results: dict[str, FetchSummary] = {}
            try:
                def on_fetch_all_progress(event: FetchProgressEvent) -> None:
                    if event.type == "subscription_start":
                        console.print(f"\n[bold cyan]{event.detail}[/bold cyan] {event.feed_name}")
                    elif event.type == "page_fetch":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "article_fetch":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "article_skip":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "waiting":
                        console.print(f"  {event.detail}")
                    elif event.type == "rate_limited":
                        console.print(f"  [yellow]{event.detail}[/yellow]")
                    elif event.type == "subscription_done":
                        console.print(f"  [green]└─ {event.detail}[/green]")

                results = await fetcher_service.fetch_all(
                    days=days, latest_count=latest_count, on_progress=on_fetch_all_progress,
                    force=force,
                )
            except RateLimitError:
                for feed_mp_id, summary in results.items():
                    _print_fetch_summary(feed_mp_id, summary)
                console.print(f"\n[yellow]已被限流，已完成 {len(results)} 个订阅[/yellow]")
                console.print("[dim]请稍后重试: wchat fetch --all[/dim]")
                return
            except AuthExpiredError:
                console.print("\n[red]Token 已失效，请重新登录: wchat login[/red]")
                return

            if not results:
                effective_date = get_effective_fetch_trade_date()
                console.print(f"[green]交易日 {effective_date} 的订阅已同步完成[/green]")
            else:
                for feed_mp_id, summary in results.items():
                    _print_fetch_summary(feed_mp_id, summary)

        elif mp_id:
            # 抓取指定公众号
            try:
                def on_fetch_progress(event: FetchProgressEvent) -> None:
                    if event.type == "page_fetch":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "article_fetch":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "article_skip":
                        console.print(f"  [dim]├─ {event.detail}[/dim]")
                    elif event.type == "waiting":
                        console.print(f"  {event.detail}")
                    elif event.type == "rate_limited":
                        console.print(f"  [yellow]{event.detail}[/yellow]")

                articles = await fetcher_service.fetch_feed(
                    mp_id,
                    days=days,
                    latest_count=latest_count,
                    on_progress=on_fetch_progress,
                )
            except RateLimitError:
                console.print(f"\n[yellow]已被限流，请稍后重试: wchat fetch {mp_id}[/yellow]")
                return
            except AuthExpiredError:
                console.print("\n[red]Token 已失效，请重新登录: wchat login[/red]")
                return
            except Exception as e:
                console.print(f"\n[red]抓取失败: {e}[/red]")
                return

            console.print(f"\n[green]抓取完成，共 {len(articles)} 篇文章[/green]")

        else:
            console.print("[red]请指定公众号 ID 或使用 --all 参数[/red]")
            console.print("用法:")
            console.print("  wchat fetch               # RSS 模式下从 RSS 源抓取")
            console.print("  wchat fetch --all         # 抓取所有订阅")
            console.print("  wchat fetch MP_WXS_xxx    # 抓取指定公众号")

    run_async(_fetch())


@click.command()
@click.argument('mp_id')
@click.argument('weight', type=click.Choice(['0', '5', '10']))
def set_weight(mp_id: str, weight: str) -> None:
    """设置公众号抓取权重。

    MP_ID: 公众号 ID
    WEIGHT: 权重值 (0=低, 5=中, 10=高)
    """
    weight_int = int(weight)

    async def _set_weight() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        feed = await subscription_service.get_subscription(mp_id)
        if not feed:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        async with db.get_session() as session:
            from sqlalchemy import update
            await session.execute(
                update(Feed).where(Feed.mp_id == mp_id).values(weight=weight_int)
            )

        weight_labels = {0: "低", 5: "中", 10: "高"}
        console.print(f"[green]已设置 {feed.name} 权重为 {weight} ({weight_labels[weight_int]})[/green]")

    run_async(_set_weight())
