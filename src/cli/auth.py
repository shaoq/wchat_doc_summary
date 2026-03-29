"""认证命令模块 - login, logout。"""

import asyncio
from typing import Any

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.api.weread import WeReadClient
from src.cli.utils import console, print_qrcode, run_async
from src.services.auth import AuthService
from src.storage.database import get_db

# 可继续轮询的中间态
_WAITING_STATES = frozenset({"waiting", "pending", "scanned"})

# 终态：应立即停止轮询
_TERMINAL_FAILURE_STATES = frozenset({"expired", "error"})


async def _poll_login_status(
    auth_service: AuthService,
    login_id: str,
    max_wait: int = 120,
    poll_interval: int = 2,
) -> dict[str, Any] | None:
    """轮询登录状态，遇到终态立即返回。

    Args:
        auth_service: 认证服务实例
        login_id: 登录会话 ID
        max_wait: 最大等待秒数
        poll_interval: 轮询间隔秒数

    Returns:
        成功/失败终态结果字典，超时返回 None
    """
    waited = 0

    while waited < max_wait:
        result = await auth_service.check_login(login_id)
        status = result.get("status", "")

        if result.get("success"):
            return result

        if status in _TERMINAL_FAILURE_STATES:
            return result

        if status not in _WAITING_STATES:
            # 未知状态也视为需要停止
            return result

        # 等待态：继续轮询
        await asyncio.sleep(poll_interval)
        waited += poll_interval

    return None


@click.command()
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
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            progress.add_task("等待扫码登录...", total=None)

            result = await _poll_login_status(auth_service, login_id)

        # 处理轮询结果
        if result is None:
            console.print("\n[red]登录超时，请重试[/red]")
            return

        status = result.get("status", "")

        if result.get("success"):
            console.print("\n[bold green]登录成功![/bold green]")
            user_info = result.get("user_info", {})
            if user_info:
                console.print(f"  用户名: {user_info.get('name', '未知')}")
            return

        if status == "expired":
            console.print("\n[red]二维码已过期，请重新执行 wchat login[/red]")
            return

        if status == "error":
            console.print(f"\n[red]登录失败: {result.get('message', '未知错误')}[/red]")
            return

        console.print(f"\n[red]登录失败: {result.get('message', '未知错误')}[/red]")

    run_async(_login())


@click.command()
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
