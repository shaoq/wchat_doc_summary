"""存储层测试 - 测试数据库操作和 CRUD 功能。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.storage.database import Database, CRUDOperations
from src.models.schema import Base, Feed, Article, Auth


class TestDatabase:
    """数据库管理测试。"""

    @pytest.fixture
    def database(self) -> Database:
        """创建数据库实例。"""
        return Database(database_url="sqlite+aiosqlite:///:memory:")

    def test_database_init(self, database: Database) -> None:
        """测试数据库初始化。"""
        assert database.database_url == "sqlite+aiosqlite:///:memory:"
        assert database._engine is None
        assert database._session_factory is None

    def test_engine_lazy_init(self, database: Database) -> None:
        """测试引擎延迟初始化。"""
        engine = database.engine

        assert database._engine is not None
        assert str(engine.url) == "sqlite+aiosqlite:///:memory:"

    def test_session_factory_lazy_init(self, database: Database) -> None:
        """测试会话工厂延迟初始化。"""
        factory = database.session_factory

        assert database._session_factory is not None

    @pytest.mark.asyncio
    async def test_init_db(self, database: Database) -> None:
        """测试数据库初始化（创建表）。"""
        with patch("config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                get_db_path=MagicMock(return_value=Path("/tmp/test.db"))
            )

            await database.init_db()

            # 验证引擎已创建
            assert database._engine is not None

    @pytest.mark.asyncio
    async def test_close(self, database: Database) -> None:
        """测试关闭数据库连接。"""
        # 先初始化引擎
        _ = database.engine

        await database.close()

        # 引用仍然存在，但已 dispose

    @pytest.mark.asyncio
    async def test_get_session(self, database: Database) -> None:
        """测试获取会话。"""
        async with database.get_session() as session:
            assert session is not None

    @pytest.mark.asyncio
    async def test_get_session_rollback_on_error(self, database: Database) -> None:
        """测试会话错误时回滚。"""
        with pytest.raises(ValueError):
            async with database.get_session() as session:
                raise ValueError("Test error")


class TestCRUDOperations:
    """CRUD 操作测试。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟会话。"""
        return AsyncMock()

    @pytest.fixture
    def feed_crud(self) -> CRUDOperations[Feed]:
        """创建 Feed CRUD 实例。"""
        return CRUDOperations(Feed)

    @pytest.mark.asyncio
    async def test_create(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试创建记录。"""
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        feed = await feed_crud.create(
            mock_session,
            {"mp_id": "MP_test", "name": "测试公众号"},
        )

        mock_session.add.assert_called_once()
        assert feed.mp_id == "MP_test"
        assert feed.name == "测试公众号"

    @pytest.mark.asyncio
    async def test_get(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试获取记录。"""
        mock_feed = Feed(id=1, mp_id="MP_test", name="测试公众号")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_feed
        mock_session.execute = AsyncMock(return_value=mock_result)

        feed = await feed_crud.get(mock_session, 1)

        assert feed is not None
        assert feed.id == 1

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试获取不存在的记录。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        feed = await feed_crud.get(mock_session, 999)

        assert feed is None

    @pytest.mark.asyncio
    async def test_get_all(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试获取所有记录。"""
        feeds = [
            Feed(id=1, mp_id="MP_1", name="公众号1"),
            Feed(id=2, mp_id="MP_2", name="公众号2"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = feeds
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await feed_crud.get_all(mock_session, skip=0, limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_update(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试更新记录。"""
        feed = Feed(id=1, mp_id="MP_test", name="旧名称")

        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        updated_feed = await feed_crud.update(
            mock_session, feed, {"name": "新名称"}
        )

        assert updated_feed.name == "新名称"

    @pytest.mark.asyncio
    async def test_delete(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试删除记录。"""
        feed = Feed(id=1, mp_id="MP_test", name="测试")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = feed
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()

        success = await feed_crud.delete(mock_session, 1)

        assert success is True
        mock_session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, feed_crud: CRUDOperations[Feed], mock_session: AsyncMock
    ) -> None:
        """测试删除不存在的记录。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        success = await feed_crud.delete(mock_session, 999)

        assert success is False


class TestModels:
    """数据模型测试。"""

    def test_feed_model(self) -> None:
        """测试 Feed 模型。"""
        feed = Feed(
            id=1,
            mp_id="MP_WXS_test",
            name="测试公众号",
            intro="这是一个测试",
            status=1,
        )

        assert feed.mp_id == "MP_WXS_test"
        assert feed.name == "测试公众号"
        assert feed.status == 1
        assert "Feed" in repr(feed)

    def test_article_model(self) -> None:
        """测试 Article 模型。"""
        article = Article(
            id=1,
            feed_id=1,
            article_id="article_123",
            title="测试文章标题",
            content="<p>内容</p>",
        )

        assert article.article_id == "article_123"
        assert article.title == "测试文章标题"
        assert "Article" in repr(article)

    def test_auth_model(self) -> None:
        """测试 Auth 模型。"""
        auth = Auth(
            id=1,
            token="test_token_abc123",
            username="test_user",
            status=1,
        )

        assert auth.token == "test_token_abc123"
        assert auth.username == "test_user"
        assert auth.status == 1
        assert "Auth" in repr(auth)


class TestGetDB:
    """get_db 函数测试。"""

    @pytest.mark.asyncio
    async def test_get_db_creates_instance(self) -> None:
        """测试 get_db 创建实例。"""
        from src.storage.database import get_db, _db

        # 重置全局实例
        import src.storage.database as db_module
        db_module._db = None

        with patch("config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="sqlite+aiosqlite:///:memory:",
                get_db_path=MagicMock(return_value=Path("/tmp/test.db")),
            )

            db = await get_db()

            assert db is not None
            assert isinstance(db, Database)

        # 清理
        db_module._db = None
