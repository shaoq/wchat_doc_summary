"""CLI 主入口模块 - 创建 main group 并注册所有命令。"""

import click

from src.cli.article import article, export, show
from src.cli.auth import login, logout
from src.cli.subscription import fetch, info, ls, set_weight, subscribe, unsubscribe
from src.cli.system import init, version
from src.cli.ai import ai
from src.cli.cls_data import cls_data
from src.cli.rss_source import rss_source


@click.group()
@click.version_option(version="0.1.0", prog_name="wchat")
def main() -> None:
    """微信公众号文章订阅系统 - CLI 工具。"""
    pass


# 注册系统命令
main.add_command(init)
main.add_command(version)

# 注册认证命令
main.add_command(login)
main.add_command(logout)

# 注册订阅命令
main.add_command(subscribe)
main.add_command(unsubscribe)
main.add_command(ls)
main.add_command(info)
main.add_command(fetch)
main.add_command(set_weight)

# 注册 RSS 源命令组
main.add_command(rss_source)

# 注册文章命令
main.add_command(show)
main.add_command(article)
main.add_command(export)

# 注册 AI 命令组
main.add_command(ai)

# 注册 CLS 数据命令组
main.add_command(cls_data)


if __name__ == "__main__":
    main()
