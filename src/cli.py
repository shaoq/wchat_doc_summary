"""CLI 入口模块 - 提供命令行交互界面。"""

import asyncio
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import qrcode
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from config.settings import get_settings
from src.api.weread import WeReadClient
from src.models.schema import Article
from src.services.ai_processor import AIProcessor
from src.services.auth import AuthService
from src.services.fetcher import FetcherService
from src.services.subscription import SubscriptionService
from src.storage.database import Database, get_db

console = Console()


def print_qrcode(url: str) -> None:
    """在终端打印 ASCII 二维码。"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # 使用 Rich 打印二维码，颜色更醒目
    console.print()
    qr.print_ascii(invert=True)
    console.print()


def run_async(coro: Any) -> Any:
    """运行异步函数的辅助函数。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 如果已有事件循环在运行，创建新的
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@click.group()
@click.version_option(version="0.1.0", prog_name="wchat")
def main() -> None:
    """微信公众号文章订阅系统 - CLI 工具。"""
    pass


@main.command()
def init() -> None:
    """初始化数据库。"""
    async def _init() -> None:
        db = await get_db()
        await db.init_db()
        console.print("[green]数据库初始化成功![/green]")

    run_async(_init())


@main.command()
def version() -> None:
    """显示版本信息。"""
    console.print("[bold blue]wchat[/bold blue] version [green]0.1.0[/green]")


@main.command()
def login() -> None:
    """登录微信读书。"""
    async def _login() -> None:
        db = await get_db()
        client = WeReadClient()
        auth_service = AuthService(client, db)

        # 检查是否已登录
        if await auth_service.is_authenticated():
            auth_info = await auth_service.get_auth_info()
            console.print("[yellow]已登录[/yellow]")
            if auth_info:
                console.print(f"  用户名: {auth_info.get('username', '未知')}")
            return

        # 获取二维码
        with console.status("[bold blue]获取登录二维码...[/bold blue]"):
            login_id, qrcode_url = await auth_service.start_login()

        console.print(f"\n[bold green]请使用微信扫描下方二维码登录:[/bold green]")
        print_qrcode(qrcode_url)

        # 轮询等待登录
        max_wait = 120  # 最长等待 2 分钟
        waited = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("等待扫码登录...", total=None)

            while waited < max_wait:
                result = await auth_service.check_login(login_id)

                if result.get("success"):
                    progress.stop()
                    console.print("\n[bold green]登录成功![/bold green]")
                    user_info = result.get("user_info", {})
                    if user_info:
                        console.print(f"  用户名: {user_info.get('name', '未知')}")
                    return

                # 等待 2 秒后重试
                await asyncio.sleep(2)
                waited += 2

        console.print("\n[red]登录超时，请重试[/red]")

    run_async(_login())


@main.command()
def logout() -> None:
    """登出微信读书。"""
    async def _logout() -> None:
        db = await get_db()
        client = WeReadClient()
        auth_service = AuthService(client, db)

        if not await auth_service.is_authenticated():
            console.print("[yellow]当前未登录[/yellow]")
            return

        await auth_service.logout()
        console.print("[green]已登出[/green]")

    run_async(_logout())


@main.command()
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

        # 检查登录状态
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
        feed = await subscription_service.add_subscription(
            mp_id=mp_id,
            name=name,
            intro=intro,
            cover=cover,
        )

        console.print(Panel(
            f"[bold]公众号名称:[/bold] {name}\n"
            f"[bold]公众号 ID:[/bold] {mp_id}\n"
            f"[bold]简介:[/bold] {intro[:100] + '...' if len(intro) > 100 else intro}",
            title="[green]订阅成功[/green]",
            border_style="green",
        ))

    run_async(_subscribe())


@main.command()
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


@main.command()
@click.option('--all', 'fetch_all', is_flag=True, help='抓取所有订阅')
@click.option('--days', 'days', type=int, default=5, help='抓取最近 N 天的文章（默认 5 天）')
@click.option('--full', 'full', is_flag=True, help='抓取全部历史文章')
@click.argument('mp_id', required=False)
def fetch(fetch_all: bool, days: int, full: bool, mp_id: str | None) -> None:
    """拉取文章。

    MP_ID: 公众号 ID（可选，不指定时需使用 --all）

    默认抓取最近 5 天的文章，    """
    # full 参数优先级高于 days
    if full:
        days = None

    async def _fetch() -> None:
        db = await get_db()
        client = WeReadClient()
        auth_service = AuthService(client, db)
        subscription_service = SubscriptionService(db)
        fetcher_service = FetcherService(client, db, subscription_service)

        # 检查登录状态
        token = await auth_service.get_current_token()
        if not token:
            console.print("[red]请先登录: wchat login[/red]")
            return

        # 显示抓取范围
        if days:
            console.print(f"[cyan]抓取范围: 最近 {days} 天[/cyan]")
        else:
            console.print("[cyan]抓取范围: 全部历史[/cyan]")

        if fetch_all:
            # 抓取所有订阅
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("抓取所有订阅...", total=None)

                results = await fetcher_service.fetch_all(days=days)

            for feed_mp_id, articles in results.items():
                if articles:
                    console.print(f"  {feed_mp_id}: {len(articles)} 篇")

        elif mp_id:
            # 抓取指定公众号
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"抓取 {mp_id}...", total=None)
                articles = await fetcher_service.fetch_feed(mp_id, days=days)

            console.print(f"\n[green]抓取完成，共 {len(articles)} 篇文章[/green]")

        else:
            console.print("[red]请指定公众号 ID 或使用 --all 参数[/red]")
            console.print("用法:")
            console.print("  wchat fetch MP_WXS_xxx    # 抓取指定公众号")
            console.print("  wchat fetch --all         # 抓取所有订阅")

    run_async(_fetch())


@main.command()
@click.option('--active-only', is_flag=True, default=True, help='只显示活跃订阅')
def ls(active_only: bool) -> None:
    """查看订阅列表。"""
    async def _ls() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        # 使用新方法获取订阅及统计数据
        feeds_with_stats = await subscription_service.list_subscriptions_with_stats(active_only=active_only)

        if not feeds_with_stats:
            console.print("[yellow]暂无订阅[/yellow]")
            return

        table = Table(title="订阅列表")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("公众号名称", style="green")
        table.add_column("公众号 ID", style="blue")
        table.add_column("文章数", style="magenta", justify="right")
        table.add_column("最近文章", style="yellow")
        table.add_column("状态", style="dim")
        table.add_column("最后同步", style="dim")

        for feed, article_count, latest_article_time in feeds_with_stats:
            status = "[green]活跃[/green]" if feed.status == 1 else "[red]停用[/red]"
            sync_time = feed.sync_time.strftime("%Y-%m-%d %H:%M") if feed.sync_time else "从未同步"
            latest_time = latest_article_time.strftime("%Y-%m-%d") if latest_article_time else "-"
            table.add_row(
                str(feed.id),
                feed.name[:20] + "..." if len(feed.name) > 20 else feed.name,
                feed.mp_id[:25] + "..." if len(feed.mp_id) > 25 else feed.mp_id,
                str(article_count),
                latest_time,
                status,
                sync_time,
            )

        console.print(table)

    run_async(_ls())


@main.command()
@click.option('--format', 'output_format', type=click.Choice(['json', 'markdown']), default='json', help='输出格式')
@click.option('--output', '-o', type=click.Path(), default='articles.json', help='输出文件路径')
@click.option('--mp-id', 'mp_id', help='指定公众号 ID（可选）')
def export(output_format: str, output: str, mp_id: str | None) -> None:
    """导出文章。"""
    async def _export() -> None:
        db = await get_db()
        subscription_service = SubscriptionService(db)

        from sqlalchemy import select
        from src.models.schema import Article, Feed

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


@main.group()
def ai() -> None:
    """AI 处理命令。"""
    pass


@ai.command()
@click.argument('article_id', type=int)
@click.option('--max-length', type=int, default=200, help='摘要最大字数')
def summarize(article_id: int, max_length: int) -> None:
    """生成文章摘要。

    ARTICLE_ID: 文章 ID
    """
    async def _summarize() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]生成摘要中...[/bold blue]"):
            try:
                summary = await processor.summarize(article_id, max_length)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]生成摘要失败: {e}[/red]")
                return

        console.print(Panel(
            summary,
            title=f"[green]文章 {article_id} 摘要[/green]",
            border_style="green",
        ))

    run_async(_summarize())


@ai.command()
@click.argument('article_id', type=int)
@click.option('--max-keywords', type=int, default=10, help='最大关键词数量')
def keywords(article_id: int, max_keywords: int) -> None:
    """提取文章关键词。

    ARTICLE_ID: 文章 ID
    """
    async def _keywords() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]提取关键词中...[/bold blue]"):
            try:
                keywords_list = await processor.extract_keywords(article_id, max_keywords)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]提取关键词失败: {e}[/red]")
                return

        console.print(Panel(
            ", ".join(keywords_list),
            title=f"[green]文章 {article_id} 关键词[/green]",
            border_style="green",
        ))

    run_async(_keywords())


@ai.command()
@click.argument('article_id', type=int)
def classify(article_id: int) -> None:
    """智能分类文章。

    ARTICLE_ID: 文章 ID
    """
    async def _classify() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]分类中...[/bold blue]"):
            try:
                category = await processor.classify(article_id)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]分类失败: {e}[/red]")
                return

        console.print(f"[green]文章 {article_id} 分类:[/green] [bold]{category}[/bold]")

    run_async(_classify())


@ai.command()
@click.argument('article_id', type=int)
def sentiment(article_id: int) -> None:
    """情感分析。

    ARTICLE_ID: 文章 ID
    """
    async def _sentiment() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]情感分析中...[/bold blue]"):
            try:
                sentiment_result = await processor.analyze_sentiment(article_id)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]情感分析失败: {e}[/red]")
                return

        # 情感标签映射
        sentiment_map = {
            "positive": ("正面", "green"),
            "negative": ("负面", "red"),
            "neutral": ("中立", "yellow"),
        }
        label, color = sentiment_map.get(sentiment_result, ("未知", "dim"))

        console.print(f"[green]文章 {article_id} 情感分析:[/green] [{color}]{label}[/{color}]")

    run_async(_sentiment())


@ai.command()
@click.option('--mp-id', 'mp_id', help='指定公众号 ID（可选）')
@click.option('--batch-size', type=int, default=10, help='批量处理数量')
def batch_summarize(mp_id: str | None, batch_size: int) -> None:
    """批量生成摘要。"""
    async def _batch_summarize() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        from sqlalchemy import select
        from src.models.schema import Article, Feed

        # 获取未生成摘要的文章
        async with db.get_session() as session:
            query = select(Article).where(Article.summary.is_(None))

            if mp_id:
                query = query.join(Feed).where(Feed.mp_id == mp_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            articles = list(result.scalars().all())

        if not articles:
            console.print("[yellow]没有需要处理的文章[/yellow]")
            return

        article_ids = [a.id for a in articles]
        console.print(f"[blue]开始处理 {len(article_ids)} 篇文章...[/blue]")

        results = await processor.batch_summarize(article_ids)

        success_count = len(results)
        console.print(f"[green]处理完成，成功: {success_count}/{len(article_ids)}[/green]")

    run_async(_batch_summarize())


@ai.command()
@click.argument('mp_id')
@click.option('--output', '-o', 'output_file', type=click.Path(), default=None, help='输出文件路径（默认: output/extract_stocks/{mp_id}_stocks_{YYMMDD}.txt）')
@click.option('--force', is_flag=False, flag_value=True, default=False, help='强制重新处理已处理的文章')
@click.option('--simple-info', is_flag=True, default=False, help='额外输出简化格式的股票列表文件')
def extract_stocks(mp_id: str, output_file: str | None, force: bool, simple_info: bool) -> None:
    """提取公众号文章中的股票信息。

    MP_ID: 公众号 ID
    """
    from datetime import datetime

    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    # 默认输出路径
    if output_file is None:
        today = datetime.now().strftime("%y%m%d")
        output_file = f"output/extract_stocks/{mp_id}_stocks_{today}.txt"

    async def _extract_stocks() -> None:
        db = await get_db()
        processor = AIProcessor(db)
        subscription_service = SubscriptionService(db)

        # 验证订阅存在
        feed = await subscription_service.get_subscription(mp_id)
        if not feed:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        from sqlalchemy import func as sql_func, select

        async with db.get_session() as session:
            # 获取文章总数
            count_result = await session.execute(
                select(sql_func.count(Article.id)).where(Article.feed_id == feed.id)
            )
            total = count_result.scalar() or 0

            if total == 0:
                console.print(f"[yellow]该公众号暂无已抓取的文章[/yellow]")
                return

            # 查询所有文章
            query = (
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            articles = list(result.scalars().all())

        console.print(f"[cyan]公众号: {feed.name}[/cyan]")
        console.print(f"[blue]文章总数: {total}[/blue]")

        if force:
            console.print("[yellow]强制模式: 重新处理所有文章[/yellow]")

        # 构建文章 ID 到文章的映射
        article_map = {a.id: a for a in articles}
        article_ids = list(article_map.keys())

        # 统计计数
        stats = {"success": 0, "skipped": 0, "failed": 0}
        results: dict[int, list[str]] = {}

        # 进度回调函数
        def on_progress(article_id: int, status: str, stocks_or_error) -> None:
            stats[status] = stats.get(status, 0) + 1
            if status == "success" and stocks_or_error:
                results[article_id] = stocks_or_error

        # 使用进度条
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("  成功: {task.fields[success]}  跳过: {task.fields[skipped]}  失败: {task.fields[failed]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "提取股票信息",
                total=len(article_ids),
                success=0,
                skipped=0,
                failed=0,
            )

            # 更新进度的回调
            def progress_callback(article_id: int, status: str, stocks_or_error) -> None:
                on_progress(article_id, status, stocks_or_error)
                article = article_map.get(article_id)
                title = article.title[:20] + "..." if article and len(article.title) > 20 else (article.title if article else "未知")
                progress.update(
                    task,
                    advance=1,
                    description=f"提取股票信息 - {title}",
                    success=stats["success"],
                    skipped=stats["skipped"],
                    failed=stats["failed"],
                )

            # 批量处理
            await processor.batch_extract_stocks(article_ids, force=force, progress_callback=progress_callback)

        # 收集所有股票
        all_stocks: set[str] = set()
        output_lines: list[str] = []

        for article in articles:
            stocks = results.get(article.id, [])
            if stocks:
                all_stocks.update(stocks)
                line = f"文章 #{article.id} 《{article.title[:30]}{'...' if len(article.title) > 30 else ''}》\n  {', '.join(stocks)}"
                output_lines.append(line)

        # 汇总
        summary = f"\n[green]处理完成: {len(results)} 篇文章，提取到 {len(all_stocks)} 只股票[/green]"
        console.print(summary)

        # 导出到文件（默认保存）
        from pathlib import Path

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"公众号: {feed.name}\n")
            f.write(f"文章总数: {total}\n")
            f.write(f"处理文章: {len(results)}\n")
            f.write(f"提取股票: {len(all_stocks)}\n")
            f.write("\n" + "=" * 50 + "\n\n")
            for line in output_lines:
                f.write(line + "\n\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"\n所有股票 ({len(all_stocks)} 只):\n")
            for stock in sorted(all_stocks):
                f.write(f"  - {stock}\n")

        console.print(f"[green]已导出到: {output_path}[/green]")

        # 输出简化格式文件
        if simple_info and all_stocks:
            info_file = f"output/extract_stocks/{mp_id}_stocks_{today}_info.txt"
            info_path = Path(info_file)
            info_path.parent.mkdir(parents=True, exist_ok=True)

            sorted_stocks = sorted(all_stocks)
            group_size = 10
            groups = [sorted_stocks[i:i + group_size] for i in range(0, len(sorted_stocks), group_size)]

            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"股票列表（共 {len(all_stocks)} 只）\n")
                f.write("=" * 50 + "\n\n")
                for idx, group in enumerate(groups, 1):
                    f.write(f"第 {idx} 组:\n")
                    f.write(", ".join(group) + "\n\n")

            console.print(f"[green]已导出简化格式到: {info_path}[/green]")

    run_async(_extract_stocks())


@ai.group()
def stocks() -> None:
    """股票信息查询命令。"""
    pass


@stocks.command('list')
@click.option('--mp-id', 'mp_id', default=None, help='指定公众号 ID（可选）')
@click.option('--limit', '-n', type=int, default=50, help='显示数量（默认 50）')
def stocks_list(mp_id: str | None, limit: int) -> None:
    """列出所有已提取的股票（按出现次数排序）。"""
    import json

    async def _stocks_list() -> None:
        db = await get_db()

        from sqlalchemy import func as sql_func, select
        from src.models.schema import Article, ArticleProcessing, Feed

        async with db.get_session() as session:
            # 构建查询
            query = (
                select(ArticleProcessing.result, Article.feed_id)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
            )

            if mp_id:
                # 过滤特定公众号
                subquery = select(Feed.id).where(Feed.mp_id == mp_id).scalar_subquery()
                query = query.where(Article.feed_id == subquery)

            result = await session.execute(query)
            rows = result.all()

        # 统计股票出现次数
        stock_counts: dict[str, int] = {}
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                for stock in stocks_list_data:
                    stock_counts[stock] = stock_counts.get(stock, 0) + 1
            except json.JSONDecodeError:
                continue

        if not stock_counts:
            console.print("[yellow]暂无股票数据[/yellow]")
            return

        # 按出现次数排序
        sorted_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        table = Table(title=f"股票列表（共 {len(stock_counts)} 只，显示前 {len(sorted_stocks)} 只）")
        table.add_column("股票名称", style="cyan")
        table.add_column("出现次数", style="green", justify="right")

        for stock, count in sorted_stocks:
            table.add_row(stock, str(count))

        console.print(table)

    run_async(_stocks_list())


@stocks.command()
@click.argument('keyword')
def search(keyword: str) -> None:
    """根据关键词搜索股票。

    KEYWORD: 搜索关键词
    """
    import json

    async def _search() -> None:
        db = await get_db()

        from sqlalchemy import select
        from src.models.schema import Article, ArticleProcessing

        async with db.get_session() as session:
            query = (
                select(ArticleProcessing.result, ArticleProcessing.article_id)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
            )
            result = await session.execute(query)
            rows = result.all()

        # 搜索匹配的股票
        matched_stocks: dict[str, int] = {}
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                for stock in stocks_list_data:
                    if keyword.lower() in stock.lower():
                        matched_stocks[stock] = matched_stocks.get(stock, 0) + 1
            except json.JSONDecodeError:
                continue

        if not matched_stocks:
            console.print(f"[yellow]未找到包含 '{keyword}' 的股票[/yellow]")
            return

        # 按出现次数排序
        sorted_stocks = sorted(matched_stocks.items(), key=lambda x: x[1], reverse=True)

        table = Table(title=f"搜索结果: '{keyword}'（找到 {len(sorted_stocks)} 只）")
        table.add_column("股票名称", style="cyan")
        table.add_column("出现次数", style="green", justify="right")

        for stock, count in sorted_stocks:
            table.add_row(stock, str(count))

        console.print(table)

    run_async(_search())


@stocks.command()
@click.argument('stock_name')
@click.option('--limit', '-n', type=int, default=20, help='显示文章数量（默认 20）')
def show(stock_name: str, limit: int) -> None:
    """显示某股票出现在哪些文章中。

    STOCK_NAME: 股票名称（支持模糊匹配）
    """
    import json

    async def _show() -> None:
        db = await get_db()

        from sqlalchemy import select
        from src.models.schema import Article, ArticleProcessing

        async with db.get_session() as session:
            query = (
                select(ArticleProcessing.result, ArticleProcessing.article_id, Article.title, Article.publish_time)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            rows = result.all()

        # 查找包含该股票的文章
        matched_articles = []
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                # 模糊匹配
                for stock in stocks_list_data:
                    if stock_name.lower() in stock.lower():
                        matched_articles.append({
                            "title": row[2],
                            "publish_time": row[3],
                            "stocks": stocks_list_data,
                        })
                        break
            except json.JSONDecodeError:
                continue

        if not matched_articles:
            console.print(f"[yellow]未找到包含 '{stock_name}' 的文章[/yellow]")
            return

        matched_articles = matched_articles[:limit]

        console.print(f"[cyan]股票: {stock_name}[/cyan]")
        console.print(f"[blue]出现在 {len(matched_articles)} 篇文章中:[/blue]\n")

        for article in matched_articles:
            publish_str = article["publish_time"].strftime("%Y-%m-%d") if article["publish_time"] else "未知日期"
            title = article["title"][:40] + "..." if len(article["title"]) > 40 else article["title"]
            console.print(f"  • 《{title}》 {publish_str}")

        if len(matched_articles) == limit:
            console.print(f"\n[dim]显示前 {limit} 篇，使用 --limit 查看更多[/dim]")

    run_async(_show())


def _format_market_data_summary(market_data: dict[str, Any]) -> str:
    """格式化市场数据为一行摘要。

    Args:
        market_data: 市场数据字典

    Returns:
        格式化的摘要字符串
    """
    indices = market_data.get("indices", {})
    volume = market_data.get("volume", {})
    stats = market_data.get("statistics", {})

    # 指数摘要
    index_parts = []
    for key in ["sh", "sz", "cy"]:
        if key in indices:
            data = indices[key]
            name = data.get("name", key)
            close = data.get("close", 0)
            change = data.get("change", 0)
            sign = "+" if change >= 0 else ""
            index_parts.append(f"{name[:2]} {close:.2f} ({sign}{change*100:.2f}%)")

    indices_str = " | ".join(index_parts) if index_parts else "无数据"

    # 成交额摘要
    total_volume = volume.get("total_volume", 0)
    if total_volume >= 10000:
        volume_str = f"{total_volume/10000:.1f}万亿"
    else:
        volume_str = f"{total_volume:.0f}亿"

    # 涨跌摘要
    up = stats.get("up_count", 0)
    down = stats.get("down_count", 0)
    flat = stats.get("flat_count", 0)

    return f"指数: {indices_str}  |  成交: {volume_str}  |  涨跌: {up}/{down}/{flat}"


def _format_articles_summary(articles: list[dict[str, Any]], days_back: int = 3) -> str:
    """格式化文章统计摘要。

    Args:
        articles: 文章列表
        days_back: 查找天数

    Returns:
        格式化的摘要字符串
    """
    count = len(articles)
    return f"找到 {count} 篇文章 (最近 {days_back} 天)"


def _format_elapsed_time(elapsed: float) -> str:
    """格式化耗时。

    Args:
        elapsed: 耗时（秒）

    Returns:
        格式化的耗时字符串
    """
    return f"{elapsed:.1f}s"


@ai.command('market-summary')
@click.option('--date', 'target_date', type=str, default=None, help='指定日期 (YYYY-MM-DD)')
@click.option('--offline', is_flag=True, help='离线模式（仅使用已抓取文章）')
@click.option('--list', 'list_summaries', is_flag=True, help='查看历史总结')
@click.option('--force', is_flag=True, help='强制重新生成（覆盖已有总结）')
def market_summary(target_date: str | None, offline: bool, list_summaries: bool, force: bool) -> None:
    """生成 A 股市场总结。

    自动获取最近一个交易日（排除周末和节假日）的市场数据，
    结合已抓取的财经公众号文章，生成结构化的市场总结报告。
    """
    from datetime import date as date_type
    from pathlib import Path

    from src.api.finance import FinanceClient
    from src.services.ai_processor import AIProcessor
    from src.services.market_analyzer import MarketAnalyzer

    async def _market_summary() -> None:
        db = await get_db()
        analyzer = MarketAnalyzer(db)
        processor = AIProcessor(db)

        # 查看历史总结
        if list_summaries:
            summaries = await analyzer.list_summaries(limit=10)
            if not summaries:
                console.print("[yellow]暂无历史总结[/yellow]")
                return

            table = Table(title="历史市场总结")
            table.add_column("日期", style="cyan")
            table.add_column("创建时间", style="green")

            for s in summaries:
                table.add_row(
                    str(s.trade_date),
                    s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_time else "未知",
                )

            console.print(table)
            return

        # 解析日期
        if target_date:
            try:
                trade_date = date_type.fromisoformat(target_date)
            except ValueError:
                console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
                return
        else:
            trade_date = analyzer.get_latest_trade_date()

        console.print(f"[bold blue]交易日: {trade_date}[/bold blue]")
        if offline:
            console.print("[yellow]离线模式[/yellow]")
        console.print()

        # 检查是否已有总结
        existing = await analyzer.get_existing_summary(trade_date)
        if existing and not force:
            console.print(f"[yellow]该交易日已有总结，使用 --force 重新生成[/yellow]")
            console.print(f"\n已保存到: output/market_summaries/{trade_date}.md")
            return

        # [1/3] 获取市场数据
        offline_label = " [yellow](离线模式)[/yellow]" if offline else ""
        with console.status(f"[bold blue][1/3] 获取市场数据...{offline_label}[/bold blue]"):
            market_data = await analyzer.collect_market_data(offline=offline)

        # 显示市场数据摘要
        if market_data.get("offline"):
            console.print("      [green]✓[/green] [yellow]离线模式: 无实时数据[/yellow]")
        else:
            summary = _format_market_data_summary(market_data)
            console.print(f"      [green]✓[/green] {summary}")
        console.print()

        # [2/3] 获取相关文章
        with console.status("[bold blue][2/3] 获取相关文章...[/bold blue]"):
            articles = await analyzer.get_related_articles(trade_date)

        # 显示文章统计
        articles_summary = _format_articles_summary(articles)
        console.print(f"      [green]✓[/green] {articles_summary}")
        console.print()

        # [3/3] AI 生成市场总结
        with console.status("[bold blue][3/3] AI 生成市场总结...[/bold blue]"):
            start_time = time.perf_counter()
            ai_failed = False
            try:
                content = await processor.generate_market_summary(
                    str(trade_date),
                    market_data,
                    articles,
                )
            except Exception as e:
                ai_failed = True
                content = await analyzer.generate_summary(trade_date, market_data, articles)
            elapsed = time.perf_counter() - start_time

        # 显示 AI 生成结果
        elapsed_str = _format_elapsed_time(elapsed)
        if ai_failed:
            console.print(f"      [green]✓[/green] [yellow]AI 生成失败，使用基础模板[/yellow] (耗时 {elapsed_str})")
        else:
            console.print(f"      [green]✓[/green] 完成 (耗时 {elapsed_str})")
        console.print()

        # 保存总结
        await analyzer.save_summary(trade_date, content, market_data)

        # 显示结果
        console.print(Panel(
            content[:2000] + "..." if len(content) > 2000 else content,
            title=f"[green]{trade_date} 市场总结[/green]",
            border_style="green",
        ))

        console.print(f"\n[green]✓[/green] 总结已保存到: output/market_summaries/{trade_date}.md")

    run_async(_market_summary())


@main.command()
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

        from sqlalchemy import select, func
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


@main.command()
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


@main.command()
@click.argument('article_id', type=int)
def article(article_id: int) -> None:
    """查看文章详情。

    ARTICLE_ID: 文章 ID
    """
    async def _article() -> None:
        db = await get_db()

        from sqlalchemy import select
        from src.models.schema import Article

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


main.add_command(ai)

if __name__ == "__main__":
    main()
