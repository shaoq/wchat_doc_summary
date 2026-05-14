"""RSS 源管理服务 - 管理 RSS 源的增删改查、健康状态和成员关系。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update

from config.settings import get_settings
from src.models.schema import RSSArticleMembership, RSSSource, RSSSourceHealth
from src.storage.database import Database

logger = logging.getLogger(__name__)


class RSSSourceService:
    """RSS 源管理服务。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ── RSS 源 CRUD ─────────────────────────────────────────────

    async def add_source(
        self,
        source_name: str,
        feed_url: str,
        source_type: str = "aggregate",
        provider: str = "rss",
        provider_source_id: str | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ) -> RSSSource:
        """添加 RSS 源。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource).where(RSSSource.source_name == source_name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.feed_url = feed_url
                existing.source_type = source_type
                existing.provider = provider
                existing.provider_source_id = provider_source_id or existing.provider_source_id
                if provider_metadata is not None:
                    existing.provider_metadata = json.dumps(provider_metadata, ensure_ascii=False)
                existing.status = 1
                await session.flush()
                await session.refresh(existing)
                logger.info("RSS 源已存在，已更新: %s", source_name)
                return existing

            source = RSSSource(
                source_name=source_name,
                source_type=source_type,
                feed_url=feed_url,
                provider=provider,
                provider_source_id=provider_source_id,
                provider_metadata=json.dumps(provider_metadata, ensure_ascii=False) if provider_metadata else None,
            )
            session.add(source)
            await session.flush()
            await session.refresh(source)
            logger.info("添加 RSS 源成功: %s", source_name)
            return source

    async def remove_source(self, source_name: str) -> bool:
        """删除 RSS 源（级联删除健康和成员记录）。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource).where(RSSSource.source_name == source_name)
            )
            source = result.scalar_one_or_none()
            if not source:
                return False
            await session.delete(source)
            logger.info("删除 RSS 源: %s", source_name)
            return True

    async def disable_source(self, source_name: str) -> bool:
        """停用 RSS 源。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                update(RSSSource)
                .where(RSSSource.source_name == source_name)
                .values(status=0)
            )
            return result.rowcount > 0

    async def enable_source(self, source_name: str) -> bool:
        """启用 RSS 源。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                update(RSSSource)
                .where(RSSSource.source_name == source_name)
                .values(status=1)
            )
            return result.rowcount > 0

    async def update_source(
        self,
        source_name: str,
        *,
        feed_url: str | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ) -> RSSSource | None:
        """更新 RSS 源配置。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource).where(RSSSource.source_name == source_name)
            )
            source = result.scalar_one_or_none()
            if not source:
                return None
            if feed_url is not None:
                source.feed_url = feed_url
            if provider_metadata is not None:
                source.provider_metadata = json.dumps(provider_metadata, ensure_ascii=False)
            await session.flush()
            await session.refresh(source)
            return source

    async def list_sources(self, active_only: bool = True) -> list[RSSSource]:
        """列出所有 RSS 源。"""
        async with self.db.get_session() as session:
            query = select(RSSSource)
            if active_only:
                query = query.where(RSSSource.status == 1)
            query = query.order_by(RSSSource.source_name.asc())
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_source(self, source_name: str) -> RSSSource | None:
        """获取单个 RSS 源。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource).where(RSSSource.source_name == source_name)
            )
            return result.scalar_one_or_none()

    async def get_source_by_id(self, source_id: int) -> RSSSource | None:
        """按 ID 获取 RSS 源。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource).where(RSSSource.id == source_id)
            )
            return result.scalar_one_or_none()

    async def count_active_sources(self) -> int:
        """统计活跃 RSS 源数量（用于计划配额检查）。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(func.count(RSSSource.id)).where(RSSSource.status == 1)
            )
            return result.scalar() or 0

    async def check_quota_warning(self) -> tuple[bool, int, int | None]:
        """检查 RSS 源配额是否超限。

        Returns:
            (is_warning, active_count, plan_limit)
            plan_limit 为 None 表示未配置限制
        """
        settings = get_settings()
        plan_limit = settings.wechat_rss_plan_limit
        active_count = await self.count_active_sources()
        if plan_limit is None:
            return False, active_count, None
        return active_count > plan_limit, active_count, plan_limit

    # ── 健康状态管理 ─────────────────────────────────────────────

    async def get_health(self, source_id: int) -> RSSSourceHealth | None:
        """获取 RSS 源健康状态。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSourceHealth).where(RSSSourceHealth.source_id == source_id)
            )
            return result.scalar_one_or_none()

    async def record_success(
        self,
        source_id: int,
        latest_item_time: datetime | None = None,
    ) -> None:
        """记录 RSS 源成功抓取。"""
        async with self.db.get_session() as session:
            health = await self._ensure_health(session, source_id)
            health.last_success_at = datetime.now()
            health.consecutive_failures = 0
            health.last_error_summary = None
            if latest_item_time:
                health.latest_item_time = latest_item_time
            await session.flush()

    async def record_failure(self, source_id: int, error_summary: str) -> None:
        """记录 RSS 源抓取失败。"""
        async with self.db.get_session() as session:
            health = await self._ensure_health(session, source_id)
            health.consecutive_failures += 1
            health.last_error_summary = error_summary[:512]
            await session.flush()

    async def record_empty(self, source_id: int) -> None:
        """记录 RSS 源返回空响应。"""
        async with self.db.get_session() as session:
            health = await self._ensure_health(session, source_id)
            health.empty_response_count += 1
            health.last_success_at = datetime.now()
            health.consecutive_failures = 0
            await session.flush()

    async def is_stale(self, source_id: int) -> bool:
        """检查 RSS 源是否过期（最新条目时间超过阈值）。"""
        settings = get_settings()
        health = await self.get_health(source_id)
        if not health or not health.latest_item_time:
            return False
        threshold = timedelta(hours=settings.rss_stale_threshold_hours)
        return datetime.now() - health.latest_item_time > threshold

    async def _ensure_health(self, session: Any, source_id: int) -> RSSSourceHealth:
        """确保健康记录存在。"""
        result = await session.execute(
            select(RSSSourceHealth).where(RSSSourceHealth.source_id == source_id)
        )
        health = result.scalar_one_or_none()
        if not health:
            health = RSSSourceHealth(source_id=source_id)
            session.add(health)
            await session.flush()
            await session.refresh(health)
        return health

    # ── 成员关系管理 ─────────────────────────────────────────────

    async def add_article_membership(
        self, article_id: int, source_id: int
    ) -> RSSArticleMembership:
        """添加文章到 RSS 源的成员关系。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSArticleMembership).where(
                    RSSArticleMembership.article_id == article_id,
                    RSSArticleMembership.source_id == source_id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
            membership = RSSArticleMembership(
                article_id=article_id, source_id=source_id
            )
            session.add(membership)
            await session.flush()
            await session.refresh(membership)
            return membership

    async def get_article_sources(self, article_id: int) -> list[RSSSource]:
        """获取文章所属的 RSS 源列表。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSSource)
                .join(RSSArticleMembership, RSSArticleMembership.source_id == RSSSource.id)
                .where(RSSArticleMembership.article_id == article_id)
            )
            return list(result.scalars().all())

    async def get_source_articles(
        self, source_id: int, limit: int = 20
    ) -> list[int]:
        """获取 RSS 源下的文章 ID 列表。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RSSArticleMembership.article_id)
                .where(RSSArticleMembership.source_id == source_id)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_source_article_count(self, source_id: int) -> int:
        """获取 RSS 源下的文章数量。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(func.count(RSSArticleMembership.id))
                .where(RSSArticleMembership.source_id == source_id)
            )
            return result.scalar() or 0

    # ── 公众号推断 ─────────────────────────────────────────────

    async def infer_public_accounts(self, source_id: int) -> dict[str, int]:
        """从 RSS 源的文章中推断公众号身份。

        Returns:
            字典: {公众号名称: 文章数量}
        """
        from src.models.schema import Article

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article.title, Article.original_url)
                .join(RSSArticleMembership, RSSArticleMembership.article_id == Article.id)
                .where(RSSArticleMembership.source_id == source_id)
            )
            articles = result.all()

        # 按 feed_id 分组统计（每个 feed 代表一个公众号）
        from src.models.schema import Feed

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Feed.name, func.count(Article.id))
                .join(RSSArticleMembership, RSSArticleMembership.article_id == Article.id)
                .join(Feed, Feed.id == Article.feed_id)
                .where(RSSArticleMembership.source_id == source_id)
                .group_by(Feed.name)
            )
            return {row[0]: row[1] for row in result.all()}
