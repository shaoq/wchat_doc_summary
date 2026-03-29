"""系统命令模块 - init, version。"""

import click
from rich.console import Console

from src.cli.utils import console, run_async
from src.storage.database import get_db


@click.command()
def init() -> None:
    """初始化数据库。"""
    async def _init() -> None:
        db = await get_db()
        await db.init_db()
        console.print("[green]数据库初始化成功![/green]")

    run_async(_init())


@click.command()
def version() -> None:
    """显示版本信息。"""
    console.print("[bold blue]wchat[/bold blue] version [green]0.1.0[/green]")
