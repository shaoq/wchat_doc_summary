"""CLI 包 - 模块化命令行界面。"""

from src.cli.main import main
from src.cli.utils import (
    format_articles_summary as _format_articles_summary,
    format_elapsed_time as _format_elapsed_time,
    format_market_data_summary as _format_market_data_summary,
)

__all__ = [
    "main",
    "_format_market_data_summary",
    "_format_articles_summary",
    "_format_elapsed_time",
]
