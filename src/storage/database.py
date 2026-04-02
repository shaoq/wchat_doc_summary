"""数据库操作模块 - 提供异步数据库连接和 CRUD 操作。"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, TypeVar

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings
from src.models.schema import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class Database:
    """数据库管理类。"""

    def __init__(self, database_url: str | None = None) -> None:
        """初始化数据库连接。

        Args:
            database_url: 数据库连接字符串，默认使用配置中的值
        """
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """获取数据库引擎。"""
        if self._engine is None:
            self._engine = create_async_engine(
                self.database_url,
                echo=False,
                future=True,
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂。"""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    async def init_db(self) -> None:
        """初始化数据库，创建所有表。"""
        # 确保数据目录存在
        settings = get_settings()
        db_path = settings.get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(self._ensure_compatible_schema)

        logger.info("数据库初始化完成")

    @staticmethod
    def _ensure_compatible_schema(sync_conn) -> None:
        """为已存在的 SQLite 数据库补齐新增列。"""
        inspector = inspect(sync_conn)

        def ensure_columns(table_name: str, columns: dict[str, str]) -> None:
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for name, ddl in columns.items():
                if name in existing:
                    continue
                sync_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))

        ensure_columns(
            "feeds",
            {
                "provider": "VARCHAR(64)",
                "provider_feed_id": "VARCHAR(255)",
                "provider_meta": "TEXT",
            },
        )
        ensure_columns(
            "articles",
            {
                "provider": "VARCHAR(64)",
                "provider_item_id": "VARCHAR(255)",
            },
        )

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._engine:
            await self._engine.dispose()
            logger.info("数据库连接已关闭")

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """获取数据库会话的上下文管理器。

        Yields:
            AsyncSession: 数据库会话
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class CRUDOperations[ModelType]:
    """通用 CRUD 操作基类。"""

    def __init__(self, model: type[ModelType]) -> None:
        """初始化 CRUD 操作。

        Args:
            model: SQLAlchemy 模型类
        """
        self.model = model

    async def create(self, session: AsyncSession, obj_in: dict[str, Any]) -> ModelType:
        """创建记录。

        Args:
            session: 数据库会话
            obj_in: 创建数据

        Returns:
            创建的模型实例
        """
        db_obj = self.model(**obj_in)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def get(self, session: AsyncSession, id: int) -> ModelType | None:
        """根据 ID 获取记录。

        Args:
            session: 数据库会话
            id: 记录 ID

        Returns:
            模型实例或 None
        """
        result = await session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """获取所有记录（分页）。

        Args:
            session: 数据库会话
            skip: 跳过的记录数
            limit: 返回的记录数

        Returns:
            模型实例列表
        """
        result = await session.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(
        self,
        session: AsyncSession,
        db_obj: ModelType,
        obj_in: dict[str, Any],
    ) -> ModelType:
        """更新记录。

        Args:
            session: 数据库会话
            db_obj: 要更新的模型实例
            obj_in: 更新数据

        Returns:
            更新后的模型实例
        """
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def delete(self, session: AsyncSession, id: int) -> bool:
        """删除记录。

        Args:
            session: 数据库会话
            id: 记录 ID

        Returns:
            是否删除成功
        """
        obj = await self.get(session, id)
        if obj:
            await session.delete(obj)
            return True
        return False


# 全局数据库实例
_db: Database | None = None


async def get_db() -> Database:
    """获取数据库实例。

    Returns:
        Database: 数据库实例
    """
    global _db
    if _db is None:
        _db = Database()
        await _db.init_db()
    return _db


async def init_db() -> None:
    """初始化数据库。"""
    db = await get_db()
    await db.init_db()
