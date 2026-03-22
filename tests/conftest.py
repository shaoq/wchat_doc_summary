"""pytest 配置和共享 fixtures。"""

import asyncio
import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
import tempfile
import os

# 设置测试环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["WEREAD_API_BASE"] = "https://test.api.com"
os.environ["OPENAI_API_KEY"] = "test_key"
os.environ["ANTHROPIC_API_KEY"] = "test_key"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环。"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> MagicMock:
    """模拟设置。"""
    settings = MagicMock()
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.weread_api_base = "https://test.api.com"
    settings.request_timeout = 30
    settings.max_retries = 3
    settings.openai_api_key = "test_openai_key"
    settings.anthropic_api_key = "test_anthropic_key"
    settings.get_db_path = MagicMock(return_value=Path("/tmp/test.db"))
    return settings


@pytest.fixture
def mock_db() -> MagicMock:
    """模拟数据库实例。"""
    db = MagicMock()
    db.get_session = MagicMock()
    return db


@pytest.fixture
def mock_weread_client() -> MagicMock:
    """模拟微信读书客户端。"""
    client = MagicMock()
    client.base_url = "https://test.api.com"
    client.token = None
    client.get_login_qrcode = AsyncMock(
        return_value={"login_id": "test_id", "qrcode_url": "https://example.com/qr.png"}
    )
    client.get_login_result = AsyncMock(return_value={"status": "waiting"})
    client.get_mp_info = AsyncMock(
        return_value={"mp_id": "MP_test", "name": "测试公众号"}
    )
    client.get_articles = AsyncMock(return_value={"articles": [], "total": 0})
    client.set_token = MagicMock()
    return client


@pytest.fixture
def sample_feed() -> dict:
    """示例订阅数据。"""
    return {
        "mp_id": "MP_WXS_test123",
        "name": "测试公众号",
        "intro": "这是一个测试公众号的简介",
        "cover": "https://example.com/cover.jpg",
        "status": 1,
    }


@pytest.fixture
def sample_article() -> dict:
    """示例文章数据。"""
    return {
        "article_id": "article_test_123",
        "title": "测试文章标题",
        "content": "<p>这是文章正文内容</p>",
        "summary": "这是文章摘要",
        "pic_url": "https://example.com/pic.jpg",
        "original_url": "https://mp.weixin.qq.com/s/test",
    }


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """临时数据库路径。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
async def async_session():
    """异步数据库会话。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session

    await engine.dispose()
