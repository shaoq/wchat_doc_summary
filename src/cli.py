"""CLI 入口模块 - 从模块化 CLI 包导入主入口。

此文件保留向后兼容性， 新代码应直接使用 src.cli.main
"""

from src.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
