"""板块趋势 CLI 命令模块 - sector-trends 子命令组。"""

import click
from rich.panel import Panel
from rich.table import Table

from src.cli.utils import console, run_async
from src.services.sector_trend_service import SectorTrendAnalyzer
from src.storage.database import get_db


@click.group(name="sector-trends")
def sector_trends() -> None:
    """板块趋势跟踪命令。"""
    pass


@sector_trends.command()
@click.option("--days", type=int, default=10, help="回看天数（默认 10）")
def discover(days: int) -> None:
    """发现候选板块。"""
    async def _discover() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        with console.status("[bold blue]发现候选板块中...[/bold blue]"):
            result = await analyzer.discover_sectors(days=days)

        console.print(f"[green]发现完成[/green]")
        console.print(f"  总发现: {result['total_discovered']} 个板块")
        console.print(f"  合并到已有: {result['merged_into_existing']} 个")
        console.print(f"  新候选: {result['new_candidates']} 个")

    run_async(_discover())


@sector_trends.command("ls")
@click.option("--status", type=str, default=None, help="状态筛选 (tracked/candidate/inactive/ignored)")
@click.option("--source", type=str, default=None, help="来源筛选")
@click.option("--active-days", type=int, default=None, help="活跃窗口天数")
@click.option("--limit", "-n", type=int, default=50, help="显示数量（默认 50）")
def list_sectors(status: str | None, source: str | None, active_days: int | None, limit: int) -> None:
    """列出板块。"""
    async def _list_sectors() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        sectors = await analyzer.list_sectors(
            status=status, source=source, active_days=active_days, limit=limit,
        )

        if not sectors:
            console.print("[yellow]暂无板块数据[/yellow]")
            return

        table = Table(title=f"板块列表（共 {len(sectors)} 个）")
        table.add_column("名称", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("来源", style="blue")
        table.add_column("最近出现", style="yellow")
        table.add_column("最近更新", style="magenta")

        for s in sectors:
            status_style = {
                "tracked": "[green]tracked[/green]",
                "candidate": "[yellow]candidate[/yellow]",
                "inactive": "[dim]inactive[/dim]",
                "ignored": "[dim]ignored[/dim]",
            }.get(s["status"], s["status"])

            table.add_row(
                s["canonical_name"],
                status_style,
                s.get("source") or "-",
                s.get("last_seen_date") or "-",
                s.get("last_updated_date") or "-",
            )

        console.print(table)

    run_async(_list_sectors())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
def init(sector: str) -> None:
    """初始化板块跟踪。"""
    async def _init() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        result = await analyzer.init_sector(sector)

        action = result["action"]
        if action == "already_tracked":
            console.print(f"[yellow]板块 '{result['canonical_name']}' 已在跟踪中[/yellow]")
        elif action == "promoted":
            console.print(f"[green]板块 '{result['canonical_name']}' 已从候选提升为跟踪[/green]")
        elif action == "created":
            console.print(f"[green]板块 '{result['canonical_name']}' 已创建为跟踪板块[/green]")

    run_async(_init())


@sector_trends.command()
@click.option("--sector", default=None, help="指定板块名称")
@click.option("--all", "update_all", is_flag=True, help="更新所有跟踪板块")
@click.option("--days", type=int, default=10, help="回看窗口天数（默认 10）")
@click.option("--force", is_flag=True, help="强制重新生成")
@click.option("--limit", type=int, default=None, help="批量更新数量限制（--all 模式）")
@click.option("--continue-on-error", is_flag=True, default=True, help="遇到错误继续更新")
def update(
    sector: str | None,
    update_all: bool,
    days: int,
    force: bool,
    limit: int | None,
    continue_on_error: bool,
) -> None:
    """更新板块趋势。"""
    if not sector and not update_all:
        console.print("[red]请指定 --sector <名称> 或 --all[/red]")
        return

    async def _update() -> None:
        from src.services.ai_processor import AIProcessor

        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        try:
            ai_processor = AIProcessor(db)
        except ValueError as e:
            console.print(f"[red]AI 初始化失败: {e}[/red]")
            return

        if update_all:
            with console.status("[bold blue]批量更新板块趋势中...[/bold blue]"):
                result = await analyzer.update_all_sector_trends(
                    limit=limit,
                    force=force,
                    continue_on_error=continue_on_error,
                    ai_processor=ai_processor,
                    days=days,
                )

            console.print(f"\n[bold]批量更新完成[/bold]")
            console.print(f"  成功: [green]{result['success']}[/green]")
            console.print(f"  跳过: [yellow]{result['skipped']}[/yellow]")
            console.print(f"  失败: [red]{result['failed']}[/red]")

            # 显示每板块结果
            if result.get("results"):
                table = Table(title="更新详情")
                table.add_column("板块", style="cyan")
                table.add_column("状态", style="green")
                table.add_column("趋势", style="yellow")
                table.add_column("强度", style="blue")
                table.add_column("倾向", style="magenta")

                for r in result["results"]:
                    action = r.get("action", "unknown")
                    if action == "updated":
                        status_text = "[green]已更新[/green]"
                    elif action == "skipped":
                        status_text = "[yellow]已跳过[/yellow]"
                    elif action == "failed":
                        status_text = f"[red]失败: {r.get('error', '')[:30]}[/red]"
                    else:
                        status_text = action

                    table.add_row(
                        r.get("sector_name", "-"),
                        status_text,
                        r.get("trend_status", "-"),
                        r.get("strength_level", "-"),
                        r.get("action_bias", "-"),
                    )

                console.print(table)
            return

        # 单板块更新
        with console.status(f"[bold blue]更新板块 '{sector}' 趋势中...[/bold blue]"):
            result = await analyzer.update_sector_trend(
                sector,
                days=days,
                ai_processor=ai_processor,
                force=force,
            )

        action = result.get("action")
        if action == "skipped":
            console.print(f"[yellow]{result.get('reason', '已跳过')}[/yellow]")
        elif action == "updated":
            console.print(f"[green]板块 '{result['sector_name']}' 趋势已更新[/green]")
            console.print(f"  日期: {result['end_date']}")
            console.print(f"  趋势: {result.get('trend_status', '-')}")
            console.print(f"  强度: {result.get('strength_level', '-')}")
            console.print(f"  倾向: {result.get('action_bias', '-')}")
            console.print(f"  报告: {result.get('output_path', '-')}")
        else:
            console.print(f"[yellow]操作结果: {action}[/yellow]")

    run_async(_update())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
def show(sector: str) -> None:
    """查看板块最新趋势。"""
    async def _show() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        result = await analyzer.show_latest(sector)

        if not result:
            console.print(f"[yellow]板块 '{sector}' 未找到[/yellow]")
            return

        if not result.get("has_summary"):
            console.print(f"[yellow]板块 '{result['sector_name']}' 暂无趋势总结[/yellow]")
            console.print(f"  状态: {result.get('status', '-')}")
            return

        console.print(f"\n[bold cyan]板块: {result['sector_name']}[/bold cyan]")
        console.print(f"  日期: {result.get('end_date', '-')}")
        console.print(f"  趋势: {result.get('trend_status', '-')}")
        console.print(f"  强度: {result.get('strength_level', '-')}")
        console.print(f"  倾向: {result.get('action_bias', '-')}")

        if result.get("output_path"):
            console.print(f"  报告路径: {result['output_path']}")

        content = result.get("content", "")
        if content:
            console.print()
            console.print(Panel(
                content[:2000] + "..." if len(content) > 2000 else content,
                title=f"[green]{result['sector_name']} 趋势报告[/green]",
                border_style="green",
            ))

    run_async(_show())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
@click.option("--limit", "-n", type=int, default=20, help="显示数量（默认 20）")
def history(sector: str, limit: int) -> None:
    """查看板块趋势历史。"""
    async def _history() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        records = await analyzer.history(sector, limit=limit)

        if not records:
            console.print(f"[yellow]板块 '{sector}' 暂无历史记录[/yellow]")
            return

        table = Table(title=f"板块 '{sector}' 趋势历史（共 {len(records)} 条）")
        table.add_column("日期", style="cyan")
        table.add_column("趋势状态", style="green")
        table.add_column("强度", style="yellow")
        table.add_column("操作倾向", style="blue")
        table.add_column("报告路径", style="dim")

        for r in records:
            table.add_row(
                r.get("end_date", "-"),
                r.get("trend_status", "-"),
                r.get("strength_level", "-"),
                r.get("action_bias", "-"),
                r.get("output_path") or "-",
            )

        console.print(table)

    run_async(_history())
