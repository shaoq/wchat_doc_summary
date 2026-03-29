"""CLI 共享工具函数。"""

import asyncio
import concurrent.futures
from typing import Any

import qrcode
from rich.console import Console

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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def format_market_data_summary(market_data: dict[str, Any]) -> str:
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


def format_articles_summary(articles: list[dict[str, Any]], days_back: int = 3) -> str:
    """格式化文章统计摘要。

    Args:
        articles: 文章列表
        days_back: 查找天数

    Returns:
        格式化的摘要字符串
    """
    count = len(articles)
    return f"找到 {count} 篇文章 (最近 {days_back} 天)"


def format_elapsed_time(elapsed: float) -> str:
    """格式化耗时。

    Args:
        elapsed: 耗时（秒）

    Returns:
        格式化的耗时字符串
    """
    return f"{elapsed:.1f}s"
