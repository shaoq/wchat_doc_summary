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
                "weight": "INTEGER DEFAULT 5",
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

        # 确保 fetch_batches 表存在（新增表）
        existing_tables = inspector.get_table_names()
        if "fetch_batches" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE fetch_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mp_id VARCHAR(128) NOT NULL,
                    batch_date DATE NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_fetch_batches_mp_date UNIQUE (mp_id, batch_date)
                )
            """))
            sync_conn.execute(text("CREATE INDEX ix_fetch_batches_mp_id ON fetch_batches (mp_id)"))
            sync_conn.execute(text("CREATE INDEX ix_fetch_batches_batch_date ON fetch_batches (batch_date)"))

        if "global_market_contexts" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE global_market_contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_a_trade_date DATE NOT NULL UNIQUE,
                    status VARCHAR(16) NOT NULL,
                    captured_at VARCHAR(64),
                    as_of VARCHAR(64),
                    session VARCHAR(32),
                    source VARCHAR(64),
                    payload TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            sync_conn.execute(
                text("CREATE INDEX ix_global_market_contexts_target_a_trade_date ON global_market_contexts (target_a_trade_date)")
            )

        # RSS 源相关表
        if "rss_sources" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE rss_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name VARCHAR(128) NOT NULL UNIQUE,
                    source_type VARCHAR(32) NOT NULL DEFAULT 'aggregate',
                    feed_url VARCHAR(1024) NOT NULL,
                    provider VARCHAR(64) NOT NULL DEFAULT 'rss',
                    provider_source_id VARCHAR(255),
                    provider_metadata TEXT,
                    status INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

        if "rss_source_health" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE rss_source_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL UNIQUE,
                    last_success_at DATETIME,
                    latest_item_time DATETIME,
                    consecutive_failures INTEGER DEFAULT 0,
                    empty_response_count INTEGER DEFAULT 0,
                    last_error_summary VARCHAR(512),
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES rss_sources(id) ON DELETE CASCADE
                )
            """))
            sync_conn.execute(
                text("CREATE INDEX ix_rss_source_health_source_id ON rss_source_health (source_id)")
            )

        if "rss_article_membership" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE rss_article_membership (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    source_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_rss_article_membership UNIQUE (article_id, source_id),
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_id) REFERENCES rss_sources(id) ON DELETE CASCADE
                )
            """))
            sync_conn.execute(
                text("CREATE INDEX ix_rss_article_membership_article_id ON rss_article_membership (article_id)")
            )
            sync_conn.execute(
                text("CREATE INDEX ix_rss_article_membership_source_id ON rss_article_membership (source_id)")
            )

        # 板块趋势跟踪相关表
        if "tracked_sectors" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE tracked_sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name VARCHAR(64) NOT NULL UNIQUE,
                    sector_code VARCHAR(16) UNIQUE,
                    aliases TEXT,
                    source_codes TEXT,
                    category VARCHAR(32),
                    status VARCHAR(16) NOT NULL DEFAULT 'candidate',
                    source VARCHAR(64),
                    first_seen_date DATE,
                    last_seen_date DATE,
                    last_updated_date DATE,
                    discovery_reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_tracked_sectors_code UNIQUE (sector_code),
                    CONSTRAINT uq_tracked_sectors_canonical_name UNIQUE (canonical_name)
                )
            """))
            sync_conn.execute(
                text("CREATE INDEX ix_tracked_sectors_status ON tracked_sectors (status)")
            )
            sync_conn.execute(
                text("CREATE INDEX ix_tracked_sectors_last_seen_date ON tracked_sectors (last_seen_date)")
            )

        if "sector_trend_summaries" not in existing_tables:
            sync_conn.execute(text("""
                CREATE TABLE sector_trend_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sector_id INTEGER NOT NULL,
                    sector_name VARCHAR(64) NOT NULL,
                    sector_code VARCHAR(16),
                    end_date DATE NOT NULL,
                    window_days INTEGER NOT NULL DEFAULT 10,
                    trend_status VARCHAR(32),
                    strength_level VARCHAR(16),
                    action_bias VARCHAR(16),
                    judgement TEXT,
                    content TEXT NOT NULL,
                    evidence_json TEXT,
                    output_path VARCHAR(512),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_sector_trend_summaries_sector_date UNIQUE (sector_id, end_date),
                    FOREIGN KEY (sector_id) REFERENCES tracked_sectors(id) ON DELETE CASCADE
                )
            """))
            sync_conn.execute(
                text("CREATE INDEX ix_sector_trend_summaries_sector_id ON sector_trend_summaries (sector_id)")
            )
            sync_conn.execute(
                text("CREATE INDEX ix_sector_trend_summaries_end_date ON sector_trend_summaries (end_date)")
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
