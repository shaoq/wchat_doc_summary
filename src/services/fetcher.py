"""文章抓取服务 - 从微信公众号抓取文章并保存到数据库。"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select

from src.api.article import fetch_article_content, parse_article_html
from src.api.providers import ArticleListProvider, create_article_list_provider
from src.api.weread import AuthExpiredError, RateLimitError, WeReadAPIError, WeReadClient
from src.models.schema import Article
from src.services.subscription import SubscriptionService
from src.storage.database import Database

from config.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_LATEST_COUNT = 10
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _parse_publish_time(time_str: str | int | datetime | None) -> datetime | None:
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

    if isinstance(time_str, datetime):
        return time_str

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


def _normalize_publish_time_for_storage(time_value: str | int | datetime | None) -> datetime | None:
    """将发布时间归一化为上海时区本地 naive datetime。

    存储 contract:
    - aware datetime / Unix 时间戳: 转为 Asia/Shanghai 后去掉 tzinfo
    - naive datetime: 视为已是本地时间，原样保留
    """
    dt = _parse_publish_time(time_value)
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt

    return dt.astimezone(SHANGHAI_TZ).replace(tzinfo=None)


def _get_publish_time_from_info(article_info: dict[str, Any]) -> datetime | None:
    """从文章信息中获取发布时间。

    兼容两种字段名：publishTime（驼峰）和 publish_time（下划线）。

    Args:
        article_info: API 返回的文章信息字典

    Returns:
        解析后的 datetime 对象，解析失败返回 None
    """
    time_str = article_info.get("publishTime") or article_info.get("publish_time")
    return _normalize_publish_time_for_storage(time_str)


class FetcherService:
    """文章抓取服务。

    负责从微信读书代理获取文章列表，抓取文章内容，并保存到数据库。
    """

    def __init__(
        self,
        weread_client: WeReadClient,
        db: Database,
        subscription_service: SubscriptionService,
        article_provider: ArticleListProvider | None = None,
    ):
        """初始化抓取服务。

        Args:
            weread_client: 微信读书 API 客户端
            db: 数据库实例
            subscription_service: 订阅服务实例
            article_provider: 可选的文章列表 Provider
        """
        self.weread_client = weread_client
        self.db = db
        self.subscription_service = subscription_service
        self._providers: dict[str, ArticleListProvider] = {}
        if article_provider is not None:
            self._providers[article_provider.name] = article_provider

    async def _get_feed_or_raise(self, mp_id: str):
        """获取订阅对象，不存在则抛错。"""
        feed = await self.subscription_service.get_subscription(mp_id)
        if not feed:
            logger.error(f"未找到订阅: {mp_id}")
            raise ValueError(f"未找到订阅: {mp_id}")
        return feed

    def _resolve_feed_provider(self, mp_id: str, provider_name: str | None) -> str | None:
        """兼容历史订阅的 Provider 推断。"""
        if provider_name:
            return provider_name
        if mp_id.startswith("MP_WXS_"):
            return "weread"
        return None

    def _get_provider(self, provider_name: str | None = None) -> ArticleListProvider:
        """获取指定 Provider，未指定时按全局配置创建。"""
        settings = get_settings()
        resolved_name = provider_name or settings.article_list_provider
        if resolved_name not in self._providers:
            self._providers[resolved_name] = create_article_list_provider(
                self.weread_client,
                provider_name=resolved_name,
            )
        return self._providers[resolved_name]

    def _extract_article_list(
        self,
        response: dict[str, Any] | list[dict[str, Any]],
        fallback_page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """从响应中提取文章列表与页大小。"""
        if isinstance(response, list):
            return response, len(response)

        if not isinstance(response, dict):
            return [], fallback_page_size

        page_size = response.get("page_size") or response.get("pageSize") or fallback_page_size
        return response.get("articles", []), page_size

    def _page_all_older_than_cutoff(
        self,
        article_list: list[dict[str, Any]],
        cutoff_time: datetime,
    ) -> bool:
        """判断一页内可解析时间的文章是否全部早于 cutoff。"""
        comparable_times = [
            _get_publish_time_from_info(article_info)
            for article_info in article_list
        ]
        comparable_times = [dt for dt in comparable_times if dt is not None]

        if not comparable_times:
            return False

        return all(dt < cutoff_time for dt in comparable_times)

    async def _get_latest_publish_time(self, feed_id: int) -> datetime | None:
        """获取指定订阅已保存文章中的最新发布时间。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article)
                .where(Article.feed_id == feed_id, Article.publish_time.is_not(None))
                .order_by(Article.publish_time.desc())
                .limit(1)
            )
            latest_article = result.scalar_one_or_none()

        return _normalize_publish_time_for_storage(latest_article.publish_time) if latest_article else None

    def _build_retry_page_sizes(self, latest_count: int) -> list[int]:
        """为默认最新文章模式生成窄窗口重试序列。"""
        sizes: list[int] = []
        current = max(1, latest_count)

        while current >= 1:
            if current not in sizes:
                sizes.append(current)
            if current == 1:
                break
            current = max(1, current // 2)

        if 3 not in sizes and latest_count >= 3:
            sizes.insert(-1, 3)

        ordered_sizes = sorted(set(sizes), reverse=True)
        return ordered_sizes

    async def _get_latest_articles_with_retry(
        self,
        mp_id: str,
        latest_count: int,
        provider: ArticleListProvider,
    ) -> tuple[list[dict[str, Any]], int]:
        """默认最新文章模式下，以窄窗口降级方式获取列表。"""
        if not provider.supports_narrow_retry:
            page = await provider.get_articles(mp_id, page=1, page_size=latest_count)
            return [article.to_article_info() for article in page.articles], page.page_size

        last_error: WeReadAPIError | None = None
        attempted_sizes: list[int] = []

        for page_size in self._build_retry_page_sizes(latest_count):
            attempted_sizes.append(page_size)
            try:
                page = await provider.get_articles(
                    mp_id,
                    page=1,
                    page_size=page_size,
                    max_retries_override=0,
                    log_http_errors=False,
                )
                article_list = [article.to_article_info() for article in page.articles]
                return article_list[:latest_count], page.page_size
            except WeReadAPIError as e:
                # 限流直接上抛，不缩小窗口重试
                if isinstance(e, RateLimitError | AuthExpiredError):
                    raise
                last_error = e
                logger.warning(
                    "默认最新文章抓取失败，尝试缩小窗口: mp_id=%s, page_size=%s, error=%s",
                    mp_id,
                    page_size,
                    e,
                )

        if last_error is not None:
            attempted = "/".join(str(size) for size in attempted_sizes)
            raise WeReadAPIError(
                f"默认最新 {latest_count} 条抓取失败；已尝试 pageSize={attempted}",
                status_code=last_error.status_code,
                response_text=last_error.response_text,
            ) from last_error

        raise WeReadAPIError("默认最新文章抓取失败")

    async def _get_article_page(
        self,
        mp_id: str,
        *,
        provider: ArticleListProvider,
        page: int,
        page_size: int,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], int]:
        provider_page = await provider.get_articles(mp_id, page=page, page_size=page_size, **kwargs)
        return [item.to_article_info() for item in provider_page.articles], provider_page.page_size

    def _get_article_storage_id(self, article_info: dict[str, Any]) -> str | None:
        """为不同 Provider 生成稳定的文章唯一键。"""
        direct_id = article_info.get("id") or article_info.get("article_id")
        if direct_id:
            return str(direct_id)

        provider = article_info.get("provider")
        provider_item_id = article_info.get("provider_item_id") or article_info.get("external_id")
        if provider and provider_item_id:
            return f"{provider}:{provider_item_id}"

        original_url = article_info.get("original_url") or article_info.get("url")
        if original_url:
            return f"url:{hashlib.sha1(str(original_url).encode('utf-8')).hexdigest()[:24]}"

        return None

    async def fetch_feed(
        self,
        mp_id: str,
        max_pages: int = 5,
        days: int | None = None,
        page_size: int | None = None,
        latest_count: int | None = None,
    ) -> list[Article]:
        """抓取指定公众号的文章。

        Args:
            mp_id: 公众号 ID
            max_pages: 最大抓取页数
            days: 抓取最近 N 天的文章，None 表示不限制
            page_size: 每页文章数量，None 表示使用配置默认值
            latest_count: 仅抓取最新 N 条文章，None 表示不启用

        Returns:
            抓取到的文章列表
        """
        if page_size is None:
            page_size = get_settings().fetch_page_size

        logger.info(
            "开始抓取公众号文章: mp_id=%s, max_pages=%s, page_size=%s, days=%s, latest_count=%s",
            mp_id,
            max_pages,
            page_size,
            days,
            latest_count,
        )

        feed = await self._get_feed_or_raise(mp_id)
        provider = self._get_provider(self._resolve_feed_provider(mp_id, feed.provider))

        articles: list[Article] = []

        # 计算时间截止点
        cutoff_time = None
        if days is not None:
            cutoff_time = datetime.now(SHANGHAI_TZ).replace(tzinfo=None) - timedelta(days=days)

        try:
            if latest_count is not None:
                article_list, _ = await self._get_latest_articles_with_retry(
                    mp_id,
                    latest_count,
                    provider,
                )
                for article_info in article_list:
                    article = await self._fetch_and_save_article(feed.id, article_info)
                    if article:
                        articles.append(article)

                await self.subscription_service.update_sync_time(mp_id)
                logger.info(f"抓取完成: {len(articles)} 篇文章")
                await self.backfill_publish_time(
                    mp_id,
                    page_size=latest_count,
                    max_pages=1,
                )
                return articles

            for page in range(1, max_pages + 1):
                # 获取文章列表
                article_list, current_page_size = await self._get_article_page(
                    mp_id,
                    provider=provider,
                    page=page,
                    page_size=page_size,
                )

                if not article_list:
                    logger.info(f"第 {page} 页无文章，停止抓取")
                    break

                # 时间过滤：检查是否所有文章都早于截止时间
                if cutoff_time and self._page_all_older_than_cutoff(article_list, cutoff_time):
                        logger.info(f"第 {page} 页所有文章都已超出时间范围，停止抓取")
                        break

                # 抓取每篇文章内容
                for article_info in article_list:
                    # 时间过滤：跳过早于截止时间的文章
                    if cutoff_time:
                        publish_time = _get_publish_time_from_info(article_info)
                        if publish_time is not None and publish_time < cutoff_time:
                            logger.debug(f"跳过早期文章: {article_info.get('title', '')}")
                            continue

                    article = await self._fetch_and_save_article(feed.id, article_info)
                    if article:
                        articles.append(article)

                # 检查是否还有更多页
                if len(article_list) < current_page_size:
                    logger.info(f"已获取所有文章，共 {page} 页")
                    break

            # 更新同步时间
            await self.subscription_service.update_sync_time(mp_id)

            logger.info(f"抓取完成: {len(articles)} 篇文章")

            # Backfill publish_time for existing articles
            await self.backfill_publish_time(mp_id)

        except (RateLimitError, AuthExpiredError):
            logger.warning(f"不可恢复错误中断抓取: {mp_id}")
            raise
        except Exception as e:
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
        article_id = self._get_article_storage_id(article_info)
        title = article_info.get("title", "无标题")
        original_url = article_info.get("original_url") or article_info.get("url")
        provider = article_info.get("provider")
        provider_item_id = article_info.get("provider_item_id") or article_info.get("external_id")
        content_html = article_info.get("content_html")

        if not article_id:
            logger.warning(f"文章缺少 ID: {title}")
            return None

        try:
            # 检查是否已存在
            async with self.db.get_session() as session:
                filters = [Article.article_id == article_id]
                if original_url:
                    filters.append(Article.original_url == original_url)
                if provider and provider_item_id:
                    filters.append(
                        and_(
                            Article.provider == provider,
                            Article.provider_item_id == str(provider_item_id),
                        )
                    )
                result = await session.execute(select(Article).where(or_(*filters)))
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"文章已存在: {title}")
                    return existing

            # 抓取文章内容
            html = content_html or await fetch_article_content(original_url or article_id)
            parsed = parse_article_html(html)

            # 保存到数据库
            async with self.db.get_session() as session:
                article = Article(
                    feed_id=feed_id,
                    article_id=article_id,
                    title=parsed.get("title") or title,
                    content=parsed.get("content"),
                    pic_url=parsed.get("cover") or article_info.get("cover"),
                    provider=provider,
                    provider_item_id=str(provider_item_id) if provider_item_id else None,
                    publish_time=(
                        _get_publish_time_from_info(article_info)
                        or _normalize_publish_time_for_storage(parsed.get("publish_time"))
                    ),
                    original_url=original_url or (f"https://mp.weixin.qq.com/s/{article_id}" if not str(article_id).startswith("url:") else None),
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
        days: int | None = None,
        latest_count: int | None = None,
    ) -> dict[str, list[Article]]:
        """抓取所有已订阅公众号的文章。

        Args:
            days: 抓取最近 N 天的文章，None 表示不限制
            latest_count: 仅抓取每个订阅的最新 N 条文章，None 表示不启用

        Returns:
            字典，key 为 mp_id，value 为文章列表
        """
        if latest_count is not None:
            logger.info(f"开始抓取所有订阅 (每个订阅最新 {latest_count} 条)")
        else:
            logger.info(f"开始抓取所有订阅 (最近 {days if days else '全部'} 天)")

        feeds = await self.subscription_service.list_subscriptions(active_only=True)
        results: dict[str, list[Article]] = {}

        for feed in feeds:
            if not feed.mp_id:
                continue
            try:
                articles = await self.fetch_feed(feed.mp_id, days=days, latest_count=latest_count)
                results[feed.mp_id] = articles
            except (RateLimitError, AuthExpiredError) as e:
                logger.warning(f"不可恢复错误中断批量抓取: {feed.name} - {e}")
                results[feed.mp_id] = []
                break
            except Exception as e:
                logger.error(f"抓取失败: {feed.name} - {e}")
                results[feed.mp_id] = []

        total = sum(len(a) for a in results.values())
        logger.info(f"全部抓取完成: {total} 篇文章")

        return results

    async def fetch_incremental(
        self,
        mp_id: str,
        max_pages: int = 5,
        page_size: int | None = None,
    ) -> list[Article]:
        """增量抓取（只获取新文章）。"""
        if page_size is None:
            page_size = get_settings().fetch_page_size

        feed = await self._get_feed_or_raise(mp_id)
        latest_time = await self._get_latest_publish_time(feed.id)
        provider = self._get_provider(self._resolve_feed_provider(mp_id, feed.provider))

        if latest_time is None:
            logger.info(f"未找到已抓取文章，增量抓取退化为全量抓取: {mp_id}")
            return await self.fetch_feed(mp_id, max_pages=max_pages, days=None, page_size=page_size)

        logger.info(f"开始增量抓取: mp_id={mp_id}, latest_time={latest_time.isoformat()}")

        articles: list[Article] = []
        should_stop = False

        for page in range(1, max_pages + 1):
            article_list, current_page_size = await self._get_article_page(
                mp_id,
                provider=provider,
                page=page,
                page_size=page_size,
            )

            if not article_list:
                break

            for article_info in article_list:
                publish_time = _get_publish_time_from_info(article_info)

                # 保守策略：缺失发布时间不作为停止依据，但仍尝试抓取和后续回填
                if publish_time is not None and publish_time <= latest_time:
                    should_stop = True
                    continue

                article = await self._fetch_and_save_article(feed.id, article_info)
                if article:
                    articles.append(article)

            if should_stop or len(article_list) < current_page_size:
                break

        await self.subscription_service.update_sync_time(mp_id)
        await self.backfill_publish_time(mp_id)
        logger.info(f"增量抓取完成: {len(articles)} 篇新文章")
        return articles

    async def backfill_publish_time(
        self,
        mp_id: str,
        page_size: int | None = None,
        max_pages: int = 5,
    ) -> int:
        """批量更新已存在文章的发布时间。

        Args:
            mp_id: 公众号 ID
            page_size: 每页文章数量，None 表示使用配置默认值
            max_pages: 最大扫描页数

        Returns:
            更新的文章数量
        """
        feed = await self._get_feed_or_raise(mp_id)
        provider = self._get_provider(self._resolve_feed_provider(mp_id, feed.provider))
        if page_size is None:
            page_size = get_settings().fetch_page_size

        # 先取出需要回填的 article_id 集合，避免持有失效 session 中的 ORM 对象
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article).where(
                    Article.feed_id == feed.id,
                    Article.publish_time.is_(None),
                )
            )
            articles = list(result.scalars().all())

        if not articles:
            logger.info(f"没有需要更新的文章: {mp_id}")
            return 0

        logger.info(f"开始更新 {len(articles)} 篇文章的发布时间")
        updates: dict[str, datetime] = {}
        unresolved_ids = {article.article_id for article in articles}

        for page in range(1, max_pages + 1):
            try:
                article_list, current_page_size = await self._get_article_page(
                    mp_id,
                    provider=provider,
                    page=page,
                    page_size=page_size,
                )

                if not article_list:
                    break

                for article_info in article_list:
                    info_id = self._get_article_storage_id(article_info)
                    if info_id not in unresolved_ids:
                        continue

                    new_time = _get_publish_time_from_info(article_info)
                    if new_time:
                        updates[info_id] = new_time
                        unresolved_ids.remove(info_id)

                if not unresolved_ids or len(article_list) < current_page_size:
                    break

            except Exception as e:
                logger.error(f"批量回填发布时间失败: page={page}, mp_id={mp_id}, error={e}")
                break

        if not updates:
            logger.info(f"未找到可回填的发布时间: {mp_id}")
            return 0

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article).where(
                    Article.feed_id == feed.id,
                    Article.article_id.in_(list(updates.keys())),
                )
            )
            db_articles = list(result.scalars().all())

            for article in db_articles:
                article.publish_time = updates[article.article_id]

            await session.flush()

        updated = len(updates)
        logger.info(f"更新完成: {updated}/{len(articles)} 篇文章")
        return updated

    async def repair_weread_publish_time(self, mp_id: str | None = None) -> int:
        """修复 weread 路径误存为 UTC naive 的文章发布时间。

        仅修复 provider 显式标记为 ``weread`` 且已有发布时间的记录。

        Args:
            mp_id: 可选，限制到单个公众号

        Returns:
            修复的记录数
        """
        feed_id: int | None = None
        if mp_id is not None:
            feed = await self._get_feed_or_raise(mp_id)
            feed_id = feed.id

        async with self.db.get_session() as session:
            query = select(Article).where(
                Article.provider == "weread",
                Article.publish_time.is_not(None),
            )
            if feed_id is not None:
                query = query.where(Article.feed_id == feed_id)

            result = await session.execute(query)
            articles = list(result.scalars().all())

            for article in articles:
                article.publish_time = article.publish_time + timedelta(hours=8)

            await session.flush()

        repaired = len(articles)
        scope = mp_id or "all-weread"
        logger.info("修复 weread 发布时间完成: scope=%s, repaired=%s", scope, repaired)
        return repaired

    async def get_mp_info_from_article(self, article_url: str) -> dict[str, Any]:
        """从文章链接获取公众号信息。

        Args:
            article_url: 微信公众号文章链接

        Returns:
            公众号信息字典，包含 mp_id, name, intro, cover 等
        """
        logger.info(f"获取公众号信息: {article_url}")

        try:
            provider = self._get_provider()
            info = (await provider.get_subscription_from_article(article_url)).to_dict()

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
        except Exception as e:
            logger.error(f"获取公众号信息失败: {e}")
            raise
