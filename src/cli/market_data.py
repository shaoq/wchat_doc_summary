"""市场数据命令模块 - market-data 子命令组。"""

from datetime import date as date_type

import click
from rich.table import Table

from src.cli.utils import console, run_async
from src.storage.database import get_db


@click.group(name="market-data")
def market_data() -> None:
    """市场数据管理命令。"""
    pass


@market_data.command()
@click.option("--date", "target_date", required=True, type=str, help="交易日期 (YYYY-MM-DD)")
def backfill(target_date: str) -> None:
    """回填历史市场数据缓存。

    从支持历史查询的数据源获取指定日期的市场数据并写入本地缓存。
    仅回填成交额、涨停股等支持历史查询的分类，跳过实时快照分类。
    不生成 AI 市场总结。
    """
    # 日期校验
    try:
        trade_date = date_type.fromisoformat(target_date)
    except ValueError:
        console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
        return

    async def _backfill() -> None:
        from src.services.market_data_backfill_service import MarketDataBackfillService

        db = await get_db()
        service = MarketDataBackfillService(db)

        console.print(f"[bold]市场数据回填[/bold]")
        console.print(f"  交易日: {trade_date}")
        console.print()

        with console.status("[bold blue]回填中...[/bold blue]"):
            result = await service.backfill(trade_date)

        # 渲染结果
        console.print(f"[bold]回填完成[/bold]")
        console.print()

        table = Table(title=f"市场数据回填结果 ({trade_date})")
        table.add_column("分类", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("记录数", justify="right")
        table.add_column("说明", style="dim")

        for outcome in result.outcomes:
            if outcome.status == "populated":
                status_text = "[green]已写入[/green]"
            elif outcome.status == "skipped_unsupported":
                status_text = "[yellow]跳过（不支持历史）[/yellow]"
            elif outcome.status == "empty":
                status_text = "[dim]空[/dim]"
            elif outcome.status == "failed":
                status_text = "[red]失败[/red]"
            else:
                status_text = outcome.status

            table.add_row(
                outcome.category,
                status_text,
                str(outcome.record_count) if outcome.record_count else "-",
                outcome.message or "-",
            )

        console.print(table)

        # 汇总
        console.print()
        summary_parts = []
        if result.total_populated:
            summary_parts.append(f"写入: [green]{result.total_populated}[/green]")
        if result.total_skipped:
            summary_parts.append(f"跳过: [yellow]{result.total_skipped}[/yellow]")
        if result.total_empty:
            summary_parts.append(f"空: [dim]{result.total_empty}[/dim]")
        if result.total_failed:
            summary_parts.append(f"失败: [red]{result.total_failed}[/red]")

        console.print(f"  {' | '.join(summary_parts)}")

        if result.is_partial:
            console.print(f"  [yellow]部分完成[/yellow] - 某些分类无数据或不支持历史查询")
        elif result.is_complete:
            console.print(f"  [green]完成[/green] - 所有支持历史的分类已写入")

    run_async(_backfill())
