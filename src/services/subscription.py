"""订阅管理服务 - 管理公众号订阅的增删改查。"""

import logging
from datetime import datetime

from sqlalchemy import case, func, select, update

from src.models.schema import Article, Feed
from src.storage.database import Database

logger = logging.getLogger(__name__)


class SubscriptionService:
    """订阅管理服务。

    提供公众号订阅的增删改查操作。
    """

    def __init__(self, db: Database):
        """初始化订阅服务。

        Args:
            db: 数据库实例
        """
        self.db = db

    async def add_subscription(
        self,
        mp_id: str,
        name: str,
        intro: str = "",
        cover: str = "",
        provider: str | None = None,
        provider_feed_id: str | None = None,
        provider_meta: str | None = None,
    ) -> Feed:
        """添加订阅。

        如果订阅已存在（通过名称判断），则激活该订阅。

        Args:
            mp_id: 公众号 ID
            name: 公众号名称
            intro: 公众号简介
            cover: 封面图片 URL
            provider: 列表 Provider
            provider_feed_id: Provider 侧订阅标识
            provider_meta: Provider 元数据

        Returns:
            创建或更新的 Feed 对象

        Raises:
            ValueError: 参数无效
        """
        if not mp_id or not name:
            raise ValueError("mp_id 和 name 不能为空")

        async with self.db.get_session() as session:
            # 检查是否已存在
            result = await session.execute(
                select(Feed).where(Feed.mp_id == mp_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # 已存在，更新信息并激活
                existing.name = name
                existing.intro = intro
                existing.cover = cover
                existing.provider = provider or existing.provider
                existing.provider_feed_id = provider_feed_id or existing.provider_feed_id
                existing.provider_meta = provider_meta or existing.provider_meta
                existing.status = 1
                await session.flush()
                await session.refresh(existing)
                logger.info(f"订阅已存在，已更新: {name}")
                return existing

            # 创建新订阅
            feed = Feed(
                mp_id=mp_id,
                name=name,
                intro=intro,
                cover=cover,
                provider=provider,
                provider_feed_id=provider_feed_id,
                provider_meta=provider_meta,
                status=1,
            )
            session.add(feed)
            await session.flush()
            await session.refresh(feed)
            logger.info(f"添加订阅成功: {name}")
            return feed

    async def remove_subscription(self, mp_id: str) -> bool:
        """取消订阅（软删除，将 status 设为 0）。

        Args:
            mp_id: 公众号 ID

        Returns:
            是否操作成功
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                update(Feed)
                .where(Feed.mp_id == mp_id)
                .values(status=0)
            )
            success = result.rowcount > 0
            if success:
                logger.info(f"取消订阅成功: {mp_id}")
            else:
                logger.warning(f"订阅不存在: {mp_id}")
            return success

    async def list_subscriptions(self, active_only: bool = True) -> list[Feed]:
        """获取订阅列表。

        Args:
            active_only: 是否只返回活跃的订阅

        Returns:
            Feed 列表
        """
        async with self.db.get_session() as session:
            query = select(Feed)
            if active_only:
                query = query.where(Feed.status == 1)
            query = query.order_by(Feed.created_at.desc())

            result = await session.execute(query)
            feeds = list(result.scalars().all())
            logger.info(f"获取订阅列表: {len(feeds)} 条记录")
            return feeds

    async def get_subscription(self, mp_id: str) -> Feed | None:
        """获取单个订阅。

        Args:
            mp_id: 公众号 ID

        Returns:
            Feed 对象或 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Feed).where(Feed.mp_id == mp_id)
            )
            feed = result.scalar_one_or_none()
            return feed

    async def update_sync_time(self, mp_id: str) -> None:
        """更新最后同步时间。

        Args:
            mp_id: 公众号 ID
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(Feed)
                .where(Feed.mp_id == mp_id)
                .values(sync_time=datetime.now())
            )
            logger.info(f"更新同步时间: {mp_id}")

    async def get_subscription_by_id(self, feed_id: int) -> Feed | None:
        """根据 ID 获取订阅。

        Args:
            feed_id: Feed ID

        Returns:
            Feed 对象或 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Feed).where(Feed.id == feed_id)
            )
            return result.scalar_one_or_none()

    async def list_subscriptions_with_stats(
        self, active_only: bool = True
    ) -> list[tuple[Feed, int, datetime | None]]:
        """获取订阅列表及统计数据。

        使用单个 SQL 聚合查询，避免 N+1 查询问题。

        Args:
            active_only: 是否只返回活跃的订阅

        Returns:
            订阅列表，每个元素为元组 (Feed, 文章数量, 最新文章时间)
        """
        async with self.db.get_session() as session:
            # 使用 LEFT JOIN + GROUP BY 获取所有订阅及其统计数据
            query = (
                select(
                    Feed,
                    func.count(Article.id).label("article_count"),
                    func.max(Article.publish_time).label("latest_article_time"),
                )
                .outerjoin(Article, Article.feed_id == Feed.id)
                .group_by(Feed.id)
                .order_by(Feed.created_at.desc())
            )
            if active_only:
                query = query.where(Feed.status == 1)

            result = await session.execute(query)
            rows = result.all()

            # 转换为元组列表 (Feed, article_count, latest_article_time)
            feeds_with_stats = []
            for row in rows:
                feed = row[0]
                article_count = row[1]
                latest_article_time = row[2]
                feeds_with_stats.append((feed, article_count, latest_article_time))

            logger.info(f"获取订阅列表（带统计）: {len(feeds_with_stats)} 条记录")
            return feeds_with_stats

    async def list_subscriptions_for_fetch(self, active_only: bool = True) -> list[Feed]:
        """获取按抓取优先级排序的订阅列表。

        排序策略:
        1. weight DESC — 高权重优先
        2. sync_time IS NULL 优先 — 未同步的先抓
        3. name ASC — 确定性排序

        Args:
            active_only: 是否只返回活跃的订阅

        Returns:
            排序后的 Feed 列表
        """
        async with self.db.get_session() as session:
            query = select(Feed)
            if active_only:
                query = query.where(Feed.status == 1)
            query = query.order_by(
                Feed.weight.desc(),
                case(
                    (Feed.sync_time.is_(None), 0),
                    else_=1,
                ),
                Feed.name.asc(),
            )
            result = await session.execute(query)
            feeds = list(result.scalars().all())
            logger.info(f"获取抓取队列: {len(feeds)} 条记录（按权重排序）")
            return feeds
