"""RSS 伪 Feed 修复服务 - 识别和修复错误的 RSS 归属。

支持三种操作模式：
- dry-run: 仅识别可疑 feed 和受影响文章，不做任何修改
- fix: 重新解析文章 URL，将文章移动到正确的公众号 feed
- report: 输出未解析项目的详细信息
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import and_, func, or_, select, update

from config.settings import get_settings
from src.api.providers import create_article_list_provider
from src.api.providers.rss_provider import redact_url
from src.api.weread import WeReadClient
from src.models.schema import Article, Feed
from src.services.rss_source import RSSSourceService
from src.services.subscription import SubscriptionService
from src.storage.database import Database

logger = logging.getLogger(__name__)

# 可疑 feed 的模式：rss: 前缀、RSS: 前缀、rss_author: 前缀、短 hash 名
_SUSPICIOUS_PATTERNS = [
    re.compile(r"^rss:"),
    re.compile(r"^RSS:"),
    re.compile(r"^rss_author:"),
    re.compile(r"^biz:"),
]


@dataclass
class SuspiciousFeed:
    """可疑的 RSS 伪 Feed。"""

    feed: Feed
    article_count: int
    reason: str


@dataclass
class RepairItem:
    """修复项：单篇文章的修复结果。"""

    article_id: int
    title: str
    original_url: str | None
    old_feed_name: str
    new_feed_name: str | None = None
    resolved: bool = False
    error: str | None = None


@dataclass
class RepairReport:
    """修复报告。"""

    suspicious_feeds: list[SuspiciousFeed] = field(default_factory=list)
    total_articles_affected: int = 0
    resolved_articles: list[RepairItem] = field(default_factory=list)
    unresolved_articles: list[RepairItem] = field(default_factory=list)
    membership_preserved: int = 0

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        lines.append(f"可疑 Feed 数: {len(self.suspicious_feeds)}")
        lines.append(f"受影响文章数: {self.total_articles_affected}")
        if self.resolved_articles:
            lines.append(f"已修复: {len(self.resolved_articles)} 篇")
        if self.unresolved_articles:
            lines.append(f"未解析: {len(self.unresolved_articles)} 篇")
        if self.membership_preserved:
            lines.append(f"保留成员关系: {self.membership_preserved} 条")
        return lines


class RSSRepairService:
    """RSS 伪 Feed 修复服务。"""

    def __init__(
        self,
        db: Database,
        subscription_service: SubscriptionService,
        weread_client: WeReadClient,
    ) -> None:
        self.db = db
        self.subscription_service = subscription_service
        self.weread_client = weread_client
        self._rss_source_service = RSSSourceService(db)

    async def identify_suspicious_feeds(self) -> list[SuspiciousFeed]:
        """识别可疑的 RSS 伪 Feed。

        可疑特征：
        - mp_id 以 rss: / RSS: / rss_author: 开头
        - 名称匹配 "RSS:xxx" 或 "未知:xxx" 模式
        - provider_feed_id 是 hash 而非真实 mp_id
        """
        results: list[SuspiciousFeed] = []

        async with self.db.get_session() as session:
            # 查找所有 RSS provider 的 feed
            result = await session.execute(
                select(Feed).where(
                    or_(
                        Feed.provider == "rss",
                        Feed.provider_feed_id.like("rss:%"),
                        Feed.provider_feed_id.like("rss_author:%"),
                        Feed.mp_id.like("rss:%"),
                    )
                )
            )
            feeds = list(result.scalars().all())

            for feed in feeds:
                reason = self._classify_feed(feed)
                if not reason:
                    continue

                # 统计文章数
                count_result = await session.execute(
                    select(func.count(Article.id)).where(Article.feed_id == feed.id)
                )
                article_count = count_result.scalar() or 0

                if article_count > 0:
                    results.append(SuspiciousFeed(
                        feed=feed,
                        article_count=article_count,
                        reason=reason,
                    ))

        return results

    def _classify_feed(self, feed: Feed) -> str | None:
        """判断 feed 是否可疑，返回原因或 None。"""
        mp_id = feed.mp_id or ""
        name = feed.name or ""
        provider_feed_id = feed.provider_feed_id or ""

        # mp_id 以 rss: 开头（hash 派生）
        if mp_id.startswith("rss:"):
            return f"mp_id 为 URL hash 派生: {mp_id[:30]}"

        # provider_feed_id 为 rss_author hash
        if provider_feed_id.startswith("rss_author:"):
            return f"provider_feed_id 为作者名 hash: {provider_feed_id}"

        # 名称匹配 RSS 前缀占位模式
        if name.startswith("RSS:") or name.startswith("未知:"):
            return f"名称为占位格式: {name[:30]}"

        # 检查 provider_meta 中的 discovery_source
        if feed.provider_meta:
            try:
                meta = json.loads(feed.provider_meta)
                if meta.get("discovery_source") == "rss_auto":
                    # 通过 RSS 自动发现创建的，可能是正确的也可能不是
                    stable_id = meta.get("stable_id", "")
                    if stable_id.startswith("rss_author:"):
                        return f"RSS 自动发现（作者名 hash）: {stable_id}"
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    async def dry_run(self) -> RepairReport:
        """干运行：识别可疑 feed 和受影响文章，不做任何修改。"""
        report = RepairReport()

        suspicious_feeds = await self.identify_suspicious_feeds()
        report.suspicious_feeds = suspicious_feeds

        async with self.db.get_session() as session:
            for sf in suspicious_feeds:
                report.total_articles_affected += sf.article_count

                # 列出受影响文章
                result = await session.execute(
                    select(Article).where(Article.feed_id == sf.feed.id).limit(20)
                )
                articles = list(result.scalars().all())

                for article in articles:
                    item = RepairItem(
                        article_id=article.id,
                        title=article.title or "无标题",
                        original_url=article.original_url,
                        old_feed_name=sf.feed.name,
                    )
                    # 检查是否有可能解析
                    if article.original_url:
                        item.resolved = False  # 需要实际调用才能确定
                    else:
                        item.error = "无 original_url"
                        report.unresolved_articles.append(item)
                        continue
                    report.resolved_articles.append(item)

        return report

    async def fix(self, *, dry_run: bool = True) -> RepairReport:
        """修复可疑 RSS 伪 Feed。

        Args:
            dry_run: True 仅报告不修改，False 执行实际修复

        Returns:
            修复报告
        """
        report = RepairReport()

        suspicious_feeds = await self.identify_suspicious_feeds()
        report.suspicious_feeds = suspicious_feeds

        if not suspicious_feeds:
            return report

        settings = get_settings()
        provider_name = settings.rss_identity_resolver_provider

        for sf in suspicious_feeds:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Article).where(Article.feed_id == sf.feed.id)
                )
                articles = list(result.scalars().all())

            report.total_articles_affected += len(articles)

            for article in articles:
                item = RepairItem(
                    article_id=article.id,
                    title=article.title or "无标题",
                    original_url=article.original_url,
                    old_feed_name=sf.feed.name,
                )

                if not article.original_url:
                    item.error = "无 original_url，无法重新解析"
                    report.unresolved_articles.append(item)
                    continue

                # 尝试通过 URL 解析正确的公众号
                try:
                    provider = create_article_list_provider(
                        self.weread_client,
                        provider_name=provider_name,
                    )
                    subscription_info = await provider.get_subscription_from_article(
                        article.original_url,
                    )
                except Exception as e:
                    item.error = f"URL 解析失败: {e}"
                    report.unresolved_articles.append(item)
                    continue

                if not subscription_info or not subscription_info.mp_id:
                    item.error = "URL 解析无结果"
                    report.unresolved_articles.append(item)
                    continue

                # 查找或创建正确的 Feed
                info_dict = subscription_info.to_dict()
                canonical_feed, _ = await self.subscription_service.add_subscription(
                    mp_id=info_dict["mp_id"],
                    name=info_dict["name"],
                    intro=info_dict.get("intro", ""),
                    cover=info_dict.get("cover", ""),
                    provider=info_dict.get("provider"),
                    provider_feed_id=info_dict.get("provider_feed_id"),
                )

                # 如果是同一个 feed，无需移动
                if canonical_feed.id == article.feed_id:
                    item.new_feed_name = canonical_feed.name
                    item.resolved = True
                    report.resolved_articles.append(item)
                    continue

                # 移动文章到正确的 feed
                if not dry_run:
                    await self._move_article(
                        article_id=article.id,
                        new_feed_id=canonical_feed.id,
                    )
                    report.membership_preserved += 1

                item.new_feed_name = canonical_feed.name
                item.resolved = True
                report.resolved_articles.append(item)

        return report

    async def _move_article(self, article_id: int, new_feed_id: int) -> None:
        """将文章移动到正确的 feed（保留成员关系）。"""
        async with self.db.get_session() as session:
            await session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(feed_id=new_feed_id)
            )
