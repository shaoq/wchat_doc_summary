"""CLS 数据命令模块 - cls 命令组及其子命令。"""

import json
from datetime import date, datetime, timedelta

import click
from rich.table import Table

from src.cli.utils import console, run_async
from src.storage.database import get_db


@click.group(name='cls')
def cls_data() -> None:
    """财联社数据命令。"""
    pass


@cls_data.command('fetch-telegraphs')
@click.option('--date', 'target_date', type=str, default=None, help='指定日期 (YYYY-MM-DD)，默认今天')
@click.option('--hours', type=int, default=24, help='回溯小时数（默认 24）')
def fetch_telegraphs(target_date: str | None, hours: int) -> None:
    """抓取财联社电报并入库。

    从远端获取指定时间范围内的 CLS 重要电报，去重后保存到本地数据库。
    """
    async def _fetch_telegraphs() -> None:
        from src.services.cls_telegraph_service import CLSTelegraphService

        db = await get_db()
        service = CLSTelegraphService(db)

        if target_date:
            try:
                dt = date.fromisoformat(target_date)
            except ValueError:
                console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
                return
        else:
            dt = date.today()

        start_dt = datetime(dt.year, dt.month, dt.day, 0, 0, 0) - timedelta(hours=hours)
        end_dt = datetime(dt.year, dt.month, dt.day, 23, 59, 59)

        start_time = int(start_dt.timestamp())
        end_time = int(end_dt.timestamp())

        console.print(f"[blue]抓取电报: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ {end_dt.strftime('%Y-%m-%d %H:%M')}[/blue]")

        with console.status("[bold blue]抓取中...[/bold blue]"):
            try:
                inserted, skipped = await service.ingest_telegraphs(start_time, end_time)
            except Exception as e:
                console.print(f"[red]抓取失败: {e}[/red]")
                return

        console.print(f"[green]完成: 新增 {inserted} 条，跳过 {skipped} 条[/green]")

    run_async(_fetch_telegraphs())


@cls_data.command('fetch-watch')
@click.option('--date', 'target_date', type=str, default=None, help='指定日期 (YYYY-MM-DD)，默认今天')
@click.option('--hours', type=int, default=24, help='回溯小时数（默认 24）')
def fetch_watch(target_date: str | None, hours: int) -> None:
    """抓取财联社看盘数据并入库。

    从远端获取指定时间范围内的 CLS 看盘数据，去重后保存到本地数据库。
    """
    async def _fetch_watch() -> None:
        from src.services.cls_watch_service import CLSWatchService

        db = await get_db()
        service = CLSWatchService(db)

        if target_date:
            try:
                dt = date.fromisoformat(target_date)
            except ValueError:
                console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
                return
        else:
            dt = date.today()

        start_dt = datetime(dt.year, dt.month, dt.day, 0, 0, 0) - timedelta(hours=hours)
        end_dt = datetime(dt.year, dt.month, dt.day, 23, 59, 59)

        start_time = int(start_dt.timestamp())
        end_time = int(end_dt.timestamp())

        console.print(f"[blue]抓取看盘数据: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ {end_dt.strftime('%Y-%m-%d %H:%M')}[/blue]")

        with console.status("[bold blue]抓取中...[/bold blue]"):
            try:
                inserted, skipped = await service.ingest_watch_data(start_time, end_time)
            except Exception as e:
                console.print(f"[red]抓取失败: {e}[/red]")
                return

        console.print(f"[green]完成: 新增 {inserted} 条，跳过 {skipped} 条[/green]")

    run_async(_fetch_watch())


@cls_data.command('list-telegraphs')
@click.option('--limit', '-n', type=int, default=20, help='显示数量（默认 20）')
@click.option('--min-level', type=click.Choice(['A', 'B', 'C'], case_sensitive=False), default=None, help='最低重要程度')
def list_telegraphs(limit: int, min_level: str | None) -> None:
    """查看本地电报数据。

    显示最近入库的 CLS 重要电报列表。
    """
    async def _list_telegraphs() -> None:
        from src.services.cls_telegraph_service import CLSTelegraphService

        db = await get_db()
        service = CLSTelegraphService(db)

        items = await service.list_telegraphs(
            min_level=min_level.upper() if min_level else None,
            limit=limit,
        )

        if not items:
            console.print("[yellow]暂无电报数据[/yellow]")
            return

        table = Table(title=f"CLS 电报（显示 {len(items)} 条）")
        table.add_column("时间", style="cyan", width=16)
        table.add_column("级别", style="green", width=4)
        table.add_column("标题", style="white", no_wrap=False)

        for item in items:
            publish_time = datetime.fromtimestamp(item.ctime).strftime("%m-%d %H:%M") if item.ctime else "未知"
            level_color = {"A": "red", "B": "yellow", "C": "dim"}.get(item.level, "dim")
            table.add_row(
                publish_time,
                f"[{level_color}]{item.level}[/{level_color}]",
                item.title[:80],
            )

        console.print(table)

    run_async(_list_telegraphs())


@cls_data.command('list-watch')
@click.option('--limit', '-n', type=int, default=20, help='显示数量（默认 20）')
def list_watch(limit: int) -> None:
    """查看本地看盘数据。

    显示最近入库的 CLS 看盘数据列表。
    """
    async def _list_watch() -> None:
        from src.services.cls_watch_service import CLSWatchService

        db = await get_db()
        service = CLSWatchService(db)

        items = await service.list_watch_data(limit=limit)

        if not items:
            console.print("[yellow]暂无看盘数据[/yellow]")
            return

        table = Table(title=f"CLS 看盘数据（显示 {len(items)} 条）")
        table.add_column("时间", style="cyan", width=16)
        table.add_column("类型", style="green", width=12)
        table.add_column("标题", style="white", no_wrap=False)
        table.add_column("关联", style="dim", width=20)

        for item in items:
            publish_time = datetime.fromtimestamp(item.ctime).strftime("%m-%d %H:%M") if item.ctime else "未知"

            # 解析关联信息
            stocks = json.loads(item.stocks) if item.stocks else []
            sectors = json.loads(item.sectors) if item.sectors else []
            related_parts = []
            if stocks:
                related_parts.append(f"股:{','.join(stocks[:3])}")
            if sectors:
                related_parts.append(f"板块:{','.join(sectors[:3])}")
            related_str = " ".join(related_parts) if related_parts else "-"

            table.add_row(
                publish_time,
                item.data_type or "-",
                item.title[:60],
                related_str[:30],
            )

        console.print(table)

    run_async(_list_watch())
