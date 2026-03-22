"""文章抓取服务 - 从微信公众号抓取文章并保存到数据库。"""

import logging
from datetime import datetime, timedelta, timedelta, timezone
from typing import Any

from sqlalchemy import select

from src.api.article import fetch_article_content, parse_article_html
from src.api.weread import WeReadAPIError, WeReadClient
from src.models.schema import Article, Feed
from src.services.subscription import SubscriptionService
from src.storage.database import Database

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _parse_publish_time(time_str: str | int | None) -> datetime | None:
    """解析发布时间字符串或时间戳。

    支持多种格式：
    - ISO 8601: "2024-01-01T12:00:00Z"
    - ISO with timezone: "2024-01-01T12:00:00+08:00"
    - Simple: "2024-01-01 12:00:00"
    - Unix timestamp (int): 1704067200

    Args:
        time_str: 时间字符串或时间戳

    Returns:
        解析后的 datetime 对象，解析失败返回 None
    """
    if not time_str:
        return None

    # 处理整数时间戳
    if isinstance(time_str, int):
        try:
            return datetime.fromtimestamp(time_str, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    try:
        # 处理 ISO 8601 格式
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    # 尝试其他常见格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    logger.warning(f"无法解析发布时间: {time_str}")
    return None


def _get_publish_time_from_info(article_info: dict[str, Any]) -> datetime | None:
    """从文章信息中获取发布时间。

    兼容两种字段名：publishTime（驼峰）和 publish_time（下划线）。

    Args:
        article_info: API 返回的文章信息字典

    Returns:
        解析后的 datetime 对象，解析失败返回 None
    """
    time_str = article_info.get("publishTime") or article_info.get("publish_time")
    return _parse_publish_time(time_str)


class FetcherService:
    """文章抓取服务。

    负责从微信读书代理获取文章列表，抓取文章内容，并保存到数据库。
    """

    def __init__(
        self,
        weread_client: WeReadClient,
        db: Database,
        subscription_service: SubscriptionService,
    ):
        """初始化抓取服务。

        Args:
            weread_client: 微信读书 API 客户端
            db: 数据库实例
            subscription_service: 订阅服务实例
        """
        self.weread_client = weread_client
        self.db = db
        self.subscription_service = subscription_service

    async def fetch_feed(
        self,
        mp_id: str,
        max_pages: int = 5,
        days: int | None = 5,
        page_size: int | None = None,
    ) -> list[Article]:
        """抓取指定公众号的文章。

        Args:
            mp_id: 公众号 ID
            max_pages: 最大抓取页数
            days: 抓取最近 N 天的文章，None 表示不限制
            page_size: 每页文章数量，None 表示使用配置默认值

        Returns:
            抓取到的文章列表
        """
        if page_size is None:
            page_size = get_settings().fetch_page_size

        logger.info(f"开始抓取公众号文章: mp_id={mp_id}, max_pages={max_pages}, page_size={page_size}, days={days}")

        # 获取订阅信息
        feed = await self.subscription_service.get_subscription(mp_id)
        if not feed:
            logger.error(f"未找到订阅: {mp_id}")
            raise ValueError(f"未找到订阅: {mp_id}")

        articles: list[Article] = []

        # 计算时间截止点
        cutoff_time = None
        if days is not None:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            for page in range(1, max_pages + 1):
                # 获取文章列表
                response = await self.weread_client.get_articles(mp_id, page, page_size)

                # 处理 API 返回列表或字典的情况
                if isinstance(response, list):
                    article_list = response
                    page_size = len(response)
                else:
                    article_list = response.get("articles", [])
                    page_size = response.get("page_size", 10)

                if not article_list:
                    logger.info(f"第 {page} 页无文章，停止抓取")
                    break

                # 时间过滤：检查是否所有文章都早于截止时间
                if cutoff_time:
                    all_older = True
                    for article_info in article_list:
                        publish_time = _get_publish_time_from_info(article_info)
                        if publish_time is None:
                            continue
                        if publish_time >= cutoff_time:
                            all_older = False
                            break
                        else:
                            all_older = False
                            break

                    if all_older:
                        logger.info(f"第 {page} 页所有文章都已超出时间范围，停止抓取")
                        break

                # 抓取每篇文章内容
                for article_info in article_list:
                    # 时间过滤：跳过早于截止时间的文章
                    if cutoff_time:
                        publish_time = _get_publish_time_from_info(article_info)
                        if publish_time is None:
                            continue
                        if publish_time < cutoff_time:
                            logger.debug(f"跳过早期文章: {article_info.get('title', '')}")
                            continue

                    article = await self._fetch_and_save_article(feed.id, article_info)
                    if article:
                        articles.append(article)

                # 检查是否还有更多页
                if len(article_list) < page_size:
                    logger.info(f"已获取所有文章，共 {page} 页")
                    break

            # 更新同步时间
            await self.subscription_service.update_sync_time(mp_id)

            logger.info(f"抓取完成: {len(articles)} 篇文章")

            # Backfill publish_time for existing articles
            await self.backfill_publish_time(feed.id)

        except WeReadAPIError as e:
            logger.error(f"API 错误: {e}")
            raise

        return articles

    async def _fetch_and_save_article(
        self,
        feed_id: int,
        article_info: dict[str, Any],
    ) -> Article | None:
        """抓取并保存单篇文章。

        Args:
            feed_id: Feed ID
            article_info: 文章基本信息（从 API 获取）

        Returns:
            保存的 Article 对象，失败返回 None
        """
        article_id = article_info.get("id") or article_info.get("article_id")
        title = article_info.get("title", "无标题")

        if not article_id:
            logger.warning(f"文章缺少 ID: {title}")
            return None

        try:
            # 检查是否已存在
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Article).where(Article.article_id == article_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"文章已存在: {title}")
                    return existing

            # 抓取文章内容
            html = await fetch_article_content(article_id)
            parsed = parse_article_html(html)

            # 保存到数据库
            async with self.db.get_session() as session:
                article = Article(
                    feed_id=feed_id,
                    article_id=article_id,
                    title=parsed.get("title") or title,
                    content=parsed.get("content"),
                    pic_url=parsed.get("cover") or article_info.get("cover"),
                    publish_time=_get_publish_time_from_info(article_info) or parsed.get("publish_time"),
                    original_url=f"https://mp.weixin.qq.com/s/{article_id}",
                )
                session.add(article)
                await session.flush()
                await session.refresh(article)

            logger.info(f"保存文章成功: {article.title[:30]}...")
            return article

        except Exception as e:
            logger.error(f"抓取文章失败: {title} - {e}")
            return None

    async def fetch_all(
        self,
        days: int | None = 5,
    ) -> dict[str, list[Article]]:
        """抓取所有已订阅公众号的文章。

        Args:
            days: 抓取最近 N 天的文章，None 表示不限制

        Returns:
            字典，key 为 mp_id，value 为文章列表
        """
        logger.info(f"开始抓取所有订阅 (最近 {days if days else '全部'} 天)")

        feeds = await self.subscription_service.list_subscriptions(active_only=True)
        results: dict[str, list[Article]] = {}

        for feed in feeds:
            if not feed.mp_id:
                continue
            try:
                articles = await self.fetch_feed(feed.mp_id, days=days)
                results[feed.mp_id] = articles
            except Exception as e:
                logger.error(f"抓取失败: {feed.name} - {e}")
                results[feed.mp_id] = []

        total = sum(len(a) for a in results.values())
        logger.info(f"全部抓取完成: {total} 篇文章")

        # Backfill publish_time for all feeds
        for feed_mp_id in results:
            if results[feed_mp_id]:
                await self.backfill_publish_time(feed_mp_id)

        return results

    async def backfill_publish_time(self, mp_id: str | None) -> None:
        """批量更新已存在文章的发布时间。

        Args:
            mp_id: 公众号 ID

        Returns:
            更新的文章数量
        """
        # 获取订阅
        feed = await self.subscription_service.get_subscription(mp_id)
        if not feed:
            logger.error(f"未找到订阅: {mp_id}")
            return 0

        # 获取该公众号下 publish_time 为空的文章
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article).where(
                    Article.feed_id == feed.id,
                    Article.publish_time.is_(None)
                )
            )
            articles = list(result.scalars().all())

        if not articles:
            logger.info(f"没有需要更新的文章: {mp_id}")
            return 0

        logger.info(f"开始更新 {len(articles)} 篇文章的发布时间")

        updated = 0
        for article in articles:
            try:
                # 获取文章信息（从 API）
                response = await self.weread_client.get_articles(mp_id, 1)
                if isinstance(response, list):
                    article_list = response
                else:
                    article_list = response.get("articles", [])

                # 查找匹配的文章
                for article_info in article_list:
                    info_id = article_info.get("id") or article_info.get("article_id")
                    if info_id == article.article_id:
                        # 获取发布时间
                        new_time = _get_publish_time_from_info(article_info)
                        if new_time:
                            article.publish_time = new_time
                            updated += 1
                        break

            except Exception as e:
                logger.error(f"更新文章发布时间失败: {article.title[:30]}... - {e}")

        await session.flush()
        logger.info(f"更新完成: {updated}/{len(articles)} 篇文章")
        return updated

    async def get_mp_info_from_article(self, article_url: str) -> dict[str, Any]:
        """增量抓取（只获取新文章）。

        检查数据库中已有的最新文章时间，只获取更新的文章。

        Args:
            mp_id: 公众号 ID

        Returns:
            新抓取的文章列表
        """
        logger.info(f"增量抓取: {mp_id}")

        # 获取订阅信息
        feed = await self.subscription_service.get_subscription(mp_id)
        if not feed:
            raise ValueError(f"未找到订阅: {mp_id}")

        # 获取数据库中最新的文章时间
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
                .limit(1)
            )
            latest_article = result.scalar_one_or_none()

        latest_time = latest_article.publish_time.replace(tzinfo=None) if latest_article else None
        logger.debug(f"最新文章时间: {latest_time}")

        articles: list[Article] = []
        page = 1
        should_stop = False

        while not should_stop:
            response = await self.weread_client.get_articles(mp_id, page)

            # 处理 API 返回列表或字典的情况
            if isinstance(response, list):
                article_list = response
            else:
                article_list = response.get("articles", [])

            if not article_list:
                break

            for article_info in article_list:
                # 检查文章时间
                publish_time = _get_publish_time_from_info(article_info)
                if publish_time is None:
                    continue
                # 移除时区信息进行比较
                publish_time_naive = publish_time.replace(tzinfo=None) if publish_time else None
                latest_time_naive = latest_time.replace(tzinfo=None) if latest_time else None

                if publish_time_naive <= latest_time_naive:
                    should_stop = True
                    continue

                article = await self._fetch_and_save_article(feed.id, article_info)
                if article:
                    articles.append(article)

            page += 1

        # 更新同步时间
        await self.subscription_service.update_sync_time(mp_id)
        logger.info(f"增量抓取完成: {len(articles)} 篇新文章")

        return articles

    async def get_mp_info_from_article(self, article_url: str) -> dict[str, Any]:
        """从文章链接获取公众号信息。

        Args:
            article_url: 微信公众号文章链接

        Returns:
            公众号信息字典，包含 mp_id, name, intro, cover 等
        """
        logger.info(f"获取公众号信息: {article_url}")

        try:
            info = await self.weread_client.get_mp_info(article_url)

            # 确保返回字典格式
            if not isinstance(info, dict):
                logger.error(f"API 返回格式错误: {type(info)}")
                raise ValueError(f"API 返回格式错误，期望字典，得到: {type(info).__name__}")

            # 验证必要字段
            if not info.get("mp_id") and not info.get("name"):
                logger.error(f"API 返回缺少必要字段: {info}")
                raise ValueError("无法获取公众号 ID 或名称")

            logger.info(f"获取成功: {info.get('name')}")
            return info
        except WeReadAPIError as e:
            logger.error(f"获取公众号信息失败: {e}")
            raise
