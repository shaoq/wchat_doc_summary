#!/usr/bin/env python3
"""
微信公众号文章订阅系统 - 启动脚本

功能:
- 环境检查和初始化
- 交互式 CLI 模式
- 后台定时抓取模式
- 日志记录和状态跟踪
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

console = Console()


def check_environment() -> bool:
    """检查运行环境"""
    errors = []

    # 检查 Python 版本
    if sys.version_info < (3, 10):
        errors.append("Python 版本需要 >= 3.10")

    # 检查 .env 文件
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        errors.append(".env 文件不存在，请复制 .env.example 并配置")

    # 检查数据库
    db_dir = PROJECT_ROOT / "data"
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

    # 检查依赖
    try:
        import httpx
        import sqlalchemy
        import click
        import rich
    except ImportError as e:
        errors.append(f"缺少依赖: {e}。请运行: pip install -e .")

    if errors:
        console.print("[red]环境检查失败:[/red]")
        for error in errors:
            console.print(f"  ✗ {error}")
        return False

    console.print("[green]环境检查通过 ✓[/green]")
    return True


def init_database():
    """初始化数据库"""
    from src.storage.database import init_db

    async def _init():
        await init_db()

    asyncio.run(_init())
    console.print("[green]数据库初始化完成 ✓[/green]")


async def check_auth_status() -> Optional[str]:
    """检查认证状态"""
    from src.storage.database import Database
    from src.models.schema import Auth
    from sqlalchemy import select

    db = Database()
    async with db.get_session() as session:
        result = await session.execute(
            select(Auth).where(Auth.status == 1).order_by(Auth.created_at.desc())
        )
        auth = result.scalar_one_or_none()
        return auth.token if auth else None


def show_status():
    """显示系统状态"""
    from src.storage.database import Database
    from src.models.schema import Feed, Article, Auth
    from sqlalchemy import select, func

    async def _show():
        db = Database()
        async with db.get_session() as session:
            # 统计数据
            feed_count = await session.scalar(
                select(func.count()).select_from(Feed).where(Feed.status == 1)
            )
            article_count = await session.scalar(
                select(func.count()).select_from(Article)
            )
            auth_count = await session.scalar(
                select(func.count()).select_from(Auth).where(Auth.status == 1)
            )

            # 最近同步的订阅
            recent_feeds = await session.execute(
                select(Feed)
                .where(Feed.status == 1)
                .order_by(Feed.sync_time.desc())
                .limit(5)
            )
            feeds = recent_feeds.scalars().all()

        # 显示状态面板
        console.print(Panel.fit(
            "[bold blue]微信公众号文章订阅系统[/bold blue]\n"
            f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="系统状态"
        ))

        # 统计表格
        stats_table = Table(title="数据统计")
        stats_table.add_column("指标", style="cyan")
        stats_table.add_column("数量", style="green")
        stats_table.add_row("活跃订阅", str(feed_count or 0))
        stats_table.add_row("文章总数", str(article_count or 0))
        stats_table.add_row("有效认证", str(auth_count or 0))
        console.print(stats_table)

        # 最近订阅
        if feeds:
            feeds_table = Table(title="最近同步的订阅")
            feeds_table.add_column("公众号名称", style="cyan")
            feeds_table.add_column("最后同步时间", style="yellow")
            for feed in feeds:
                sync_time = feed.sync_time.strftime("%Y-%m-%d %H:%M") if feed.sync_time else "未同步"
                feeds_table.add_row(feed.name, sync_time)
            console.print(feeds_table)

    asyncio.run(_show())


async def fetch_all_with_progress(mp_id: str | None = None):
    """带进度条的全量抓取

    Args:
        mp_id: 指定公众号 ID，只抓取该公众号。为 None 时抓取所有订阅。
    """
    from src.services.fetcher import FetcherService
    from src.services.subscription import SubscriptionService
    from src.api.weread import WeReadClient
    from src.storage.database import Database
    from config.settings import settings

    token = await check_auth_status()
    if not token:
        console.print("[red]未登录，请先运行: wchat login[/red]")
        return

    db = Database()
    client = WeReadClient(base_url=settings.weread_api_base, token=token)
    subscription_service = SubscriptionService(db)
    fetcher = FetcherService(client, db, subscription_service)

    # 获取订阅列表
    subscriptions = await subscription_service.list_subscriptions()

    # 如果指定了 mp_id， 只抓取该公众号
    if mp_id:
        subscriptions = [s for s in subscriptions if s.mp_id == mp_id]
        if not subscriptions:
            console.print(f"[yellow]未找到公众号: {mp_id}[/yellow]")
            return

    if not subscriptions:
        console.print("[yellow]没有订阅的公众号[/yellow]")
        return

    console.print(f"[cyan]开始抓取 {len(subscriptions)} 个公众号的文章...[/cyan]")

    results = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for feed in subscriptions:
            task = progress.add_task(f"抓取 {feed.name}...", total=None)
            try:
                articles = await fetcher.fetch_feed(feed.mp_id, max_pages=3)
                results[feed.name] = len(articles)
                progress.update(task, description=f"✓ {feed.name}: {len(articles)} 篇文章")
            except Exception as e:
                progress.update(task, description=f"✗ {feed.name}: {str(e)}")
                results[feed.name] = 0

    # 显示结果
    table = Table(title="抓取结果")
    table.add_column("公众号", style="cyan")
    table.add_column("文章数", style="green")
    total = 0
    for name, count in results.items():
        table.add_row(name, str(count))
        total += count
    table.add_row("[bold]总计[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


@click.group()
def cli():
    """微信公众号文章订阅系统 - 启动脚本"""
    pass


@cli.command()
def check():
    """检查运行环境"""
    check_environment()


@cli.command()
def init():
    """初始化系统"""
    if not check_environment():
        return
    init_database()
    console.print("[green]系统初始化完成！[/green]")
    console.print("\n下一步:")
    console.print("  1. 配置 .env 文件（可选配置 AI API Key）")
    console.print("  2. 运行 [cyan]wchat login[/cyan] 登录微信读书")
    console.print("  3. 运行 [cyan]wchat subscribe <文章URL>[/cyan] 订阅公众号")


@cli.command()
def status():
    """显示系统状态"""
    if not check_environment():
        return
    show_status()


@cli.command()
@click.option("--daemon", "-d", is_flag=True, help="后台运行模式")
@click.argument("mp_id", required=False)
def fetch(daemon: bool, mp_id: str | None):
    """抓取文章"""
    if not check_environment():
        return

    if daemon:
        console.print("[yellow]后台模式启动中...[/yellow]")
        # TODO: 实现后台守护进程
        console.print("[red]后台模式尚未实现[/red]")
    else:
        asyncio.run(fetch_all_with_progress(mp_id))


@cli.command()
@click.option("--interval", "-i", default=60, help="定时抓取间隔（分钟）")
def scheduler(interval: int):
    """启动定时抓取服务"""
    import signal

    if not check_environment():
        return

    console.print(Panel.fit(
        f"[bold green]定时抓取服务启动[/bold green]\n"
        f"抓取间隔: {interval} 分钟",
        title="调度器"
    ))

    shutdown = False

    def signal_handler(sig, frame):
        nonlocal shutdown
        console.print("\n[yellow]收到停止信号，正在关闭...[/yellow]")
        shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    async def run_scheduler():
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()

        async def fetch_job():
            console.print(f"\n[cyan]{datetime.now().strftime('%H:%M:%S')} 开始定时抓取...[/cyan]")
            await fetch_all_with_progress()

        scheduler.add_job(fetch_job, 'interval', minutes=interval)
        scheduler.start()

        console.print("[green]调度器已启动，按 Ctrl+C 停止[/green]")

        # 首次立即执行
        await fetch_job()

        while not shutdown:
            await asyncio.sleep(1)

        scheduler.shutdown()
        console.print("[green]调度器已停止[/green]")

    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        pass


@cli.command()
def interactive():
    """交互式 CLI 模式"""
    import subprocess

    if not check_environment():
        return

    console.print(Panel.fit(
        "[bold blue]交互式 CLI 模式[/bold blue]\n"
        "输入命令或 'help' 查看帮助，'exit' 退出",
        title="wchat"
    ))

    while True:
        try:
            cmd = console.input("[cyan]wchat>[/cyan] ").strip()
            if not cmd:
                continue

            if cmd.lower() in ("exit", "quit", "q"):
                console.print("[yellow]再见！[/yellow]")
                break

            if cmd.lower() == "help":
                console.print("""
可用命令:
  login              登录微信读书
  subscribe <url>    订阅公众号
  unsubscribe <id>   取消订阅
  fetch [--all]      抓取文章
  list               查看订阅列表
  status             显示系统状态
  exit               退出
""")
                continue

            if cmd.lower() == "status":
                show_status()
                continue

            # 调用 wchat CLI
            result = subprocess.run(
                ["wchat"] + cmd.split(),
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True
            )
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]按 Ctrl+C 退出[/yellow]")
        except Exception as e:
            console.print(f"[red]错误: {e}[/red]")


if __name__ == "__main__":
    cli()
