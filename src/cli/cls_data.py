"""CLS 数据命令模块 - cls 命令组及其子命令。"""

import json
from datetime import date, datetime, timedelta

import click
from rich.table import Table

from src.cli.utils import console, run_async
from src.storage.database import get_db
from src.cli.cls_export import (
    CLSExportResult,
    build_cls_export_html,
    build_cls_export_path,
    discover_local_dates,
    query_telegraphs_for_date,
    query_watch_for_date,
    write_export,
)


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


@cls_data.command('export')
@click.option('--date', 'target_date', type=str, default=None, help='指定日期 (YYYY-MM-DD)，默认今天')
@click.option('--all', 'export_all', is_flag=True, help='导出所有本地日期')
@click.option('--type', 'export_type', type=click.Choice(['all', 'telegraphs', 'watch'], case_sensitive=False), default='all', help='导出数据类型（默认 all）')
@click.option('--output', 'output_path', type=click.Path(), default=None, help='自定义输出路径（仅单日期）')
@click.option('--force', is_flag=True, help='强制覆盖已存在的文件')
def export_cls(target_date: str | None, export_all: bool, export_type: str, output_path: str | None, force: bool) -> None:
    """导出本地 CLS 数据为每日 HTML 文件。

    默认导出当天的所有类型数据。使用 --all 导出所有日期。
    """
    # 参数校验
    if export_all and target_date:
        console.print("[red]不能同时指定 --date 和 --all[/red]")
        return

    if export_all and output_path:
        console.print("[red]--output 不能与 --all 一起使用[/red]")
        return

    export_type = export_type.lower()
    mode_label = "强制重建" if force else "增量"

    async def _do_export() -> None:
        db = await get_db()

        if export_all:
            await _export_all_dates(db, export_type, mode_label, force)
        else:
            dt: date
            if target_date:
                try:
                    dt = date.fromisoformat(target_date)
                except ValueError:
                    console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
                    return
            else:
                dt = date.today()

            custom_path = output_path
            await _export_single_date(db, dt, export_type, mode_label, force, custom_path)

    run_async(_do_export())


async def _export_single_date(
    db,
    target_date: date,
    export_type: str,
    mode_label: str,
    force: bool,
    custom_output: str | None = None,
) -> CLSExportResult:
    """导出单个日期的 CLS 数据。"""
    console.print(f"日期: {target_date.isoformat()}")
    console.print(f"类型: {export_type}")
    console.print(f"模式: {mode_label}")

    # 查询数据
    telegraphs = []
    watch_items = []
    if export_type in ("all", "telegraphs"):
        telegraphs = await query_telegraphs_for_date(db, target_date)
    if export_type in ("all", "watch"):
        watch_items = await query_watch_for_date(db, target_date)

    # 确定输出路径
    if custom_output:
        out_path = __import__('pathlib').Path(custom_output)
    else:
        out_path = build_cls_export_path(target_date, export_type)

    console.print(f"输出: {out_path}")

    # 无数据时不生成空文件
    if not telegraphs and not watch_items:
        console.print("[yellow]无匹配数据，跳过导出[/yellow]")
        return CLSExportResult(
            target_date=target_date,
            export_type=export_type,
            output_path=out_path,
            no_data=True,
        )

    # 构建 HTML
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = build_cls_export_html(target_date, export_type, telegraphs, watch_items, generated_at)

    # 写入文件
    written = write_export(out_path, content, force)
    if written:
        console.print(f"[green]导出完成: {len(telegraphs)} 条电报, {len(watch_items)} 条看盘数据[/green]")
        return CLSExportResult(
            target_date=target_date,
            export_type=export_type,
            output_path=out_path,
            telegraph_count=len(telegraphs),
            watch_count=len(watch_items),
            exported=True,
        )
    else:
        console.print(f"[yellow]已跳过（文件已存在）: {out_path}[/yellow]")
        return CLSExportResult(
            target_date=target_date,
            export_type=export_type,
            output_path=out_path,
            telegraph_count=len(telegraphs),
            watch_count=len(watch_items),
            skipped=True,
        )


async def _export_all_dates(
    db,
    export_type: str,
    mode_label: str,
    force: bool,
) -> None:
    """导出所有本地日期的 CLS 数据。"""
    from src.cli.cls_export import EXPORT_DIR

    dates = await discover_local_dates(db, export_type)

    if not dates:
        console.print("[yellow]本地无匹配的 CLS 数据[/yellow]")
        return

    total_dates = len(dates)
    console.print(f"批量导出: {total_dates} 个日期")
    console.print(f"类型: {export_type}")
    console.print(f"模式: {mode_label}")
    console.print(f"输出目录: {EXPORT_DIR}")
    console.print("")

    agg_exported = 0
    agg_skipped = 0
    agg_no_data = 0
    agg_telegraphs = 0
    agg_watch = 0

    for idx, d in enumerate(dates, start=1):
        console.print(f"[{idx}/{total_dates}] {d.isoformat()}")

        result = await _export_single_date(db, d, export_type, mode_label, force)

        if result.no_data:
            agg_no_data += 1
        elif result.exported:
            agg_exported += 1
            agg_telegraphs += result.telegraph_count
            agg_watch += result.watch_count
        elif result.skipped:
            agg_skipped += 1
            agg_telegraphs += result.telegraph_count
            agg_watch += result.watch_count

        console.print("")

    # 汇总
    console.print("[bold]总计[/bold]")
    console.print(f"  日期总数: {total_dates}")
    console.print(f"  导出: {agg_exported}")
    console.print(f"  跳过: {agg_skipped}")
    console.print(f"  无数据: {agg_no_data}")
    console.print(f"  电报总数: {agg_telegraphs}")
    console.print(f"  看盘数据总数: {agg_watch}")
