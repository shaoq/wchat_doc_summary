"""测试模块初始化文件。"""

import pytest

# pytest-asyncio 配置
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config: pytest.Config) -> None:
    """配置 pytest。"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test."
    )
