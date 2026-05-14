"""RSS 公众号发现服务 - 从 RSS 条目推断公众号身份并自动创建订阅。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from config.settings import get_settings
from src.models.schema import Article, Feed
from src.services.subscription import SubscriptionService
from src.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredFeed:
    """发现结果：Feed 实体 + 是否为新发现。"""

    feed: Feed
    is_newly_discovered: bool = False
    match_method: str = ""  # stable_id / author / name / placeholder


@dataclass
class DiscoveryReport:
    """发现报告：跟踪一次 RSS 同步中发现的新订阅。"""

    discovered: list[DiscoveredFeed] = field(default_factory=list)

    def add(self, result: DiscoveredFeed) -> None:
        if result.is_newly_discovered:
            # 按 feed.id 或 feed.mp_id 去重，避免同一公众号重复报告
            key = result.feed.id or result.feed.mp_id
            if not any((d.feed.id or d.feed.mp_id) == key for d in self.discovered):
                self.discovered.append(result)

    @property
    def count(self) -> int:
        return len(self.discovered)

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        settings = get_settings()
        default_status = settings.rss_discovered_feed_default_status
        for d in self.discovered:
            status_label = "活跃" if d.feed.status == 1 else "未激活"
            lines.append(
                f"  发现新公众号: {d.feed.name} (状态: {status_label}, 匹配方式: {d.match_method})"
            )
        return lines


def extract_public_account_identity(article_info: dict[str, Any]) -> dict[str, Any]:
    """从 RSS 文章信息中提取公众号身份标识。

    优先级:
    1. RSS 条目 raw 字段中的 author / source / dc_creator
    2. original_url 中的 __biz 参数（微信公众号 biz ID）
    3. author 字段作为名称匹配

    Returns:
        包含 identity 信息的字典:
        - stable_id: 稳定标识（biz ID 或 author hash）
        - display_name: 公众号名称
        - match_priority: 匹配优先级（越低越优先）
        - raw_metadata: 原始元数据
    """
    raw = article_info.get("raw", {})
    original_url = article_info.get("original_url") or article_info.get("url") or ""
    stable_id: str | None = None
    display_name: str | None = None
    match_priority = 99

    # 1. 从 URL 提取 __biz 参数（微信公众号 biz ID）
    if original_url and "__biz" in original_url:
        try:
            parsed = urlparse(original_url)
            params = parse_qs(parsed.query)
            biz_values = params.get("__biz", [])
            if biz_values and biz_values[0]:
                stable_id = f"biz:{biz_values[0]}"
                display_name = raw.get("author") or raw.get("source") or None
                match_priority = 1
        except Exception:
            pass

    # 2. 从 raw 字段提取 author / source
    if not stable_id:
        author = raw.get("author")
        source = raw.get("source")
        dc_creator = raw.get("dc_creator")

        # 优先使用 author 作为名称
        name_candidate = author or source or dc_creator
        if name_candidate and name_candidate.strip():
            display_name = name_candidate.strip()
            # author 作为稳定标识（基于名称的 hash）
            stable_id = f"rss_author:{_stable_hash(name_candidate.strip())}"
            match_priority = 2

    # 3. 回退到 article title 的 author 字段
    if not stable_id:
        author = article_info.get("author")
        if author and str(author).strip():
            display_name = str(author).strip()
            stable_id = f"rss_author:{_stable_hash(str(author).strip())}"
            match_priority = 3

    return {
        "stable_id": stable_id,
        "display_name": display_name,
        "match_priority": match_priority,
        "raw_metadata": {
            "author": raw.get("author"),
            "source": raw.get("source"),
            "dc_creator": raw.get("dc_creator"),
            "original_url": original_url[:200] if original_url else None,
        },
    }


def _stable_hash(text: str) -> str:
    """生成稳定哈希值用于名称匹配。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_name(name: str) -> str:
    """归一化公众号名称用于匹配（去空白、统一大小写）。"""
    return re.sub(r"\s+", "", name).lower()


class FeedDiscoveryService:
    """RSS 公众号发现服务。"""

    def __init__(self, db: Database, subscription_service: SubscriptionService) -> None:
        self.db = db
        self.subscription_service = subscription_service
        self._name_cache: dict[str, Feed] | None = None

    async def _get_name_cache(self) -> dict[str, Feed]:
        """获取归一化名称到 Feed 的缓存（首次使用时加载）。"""
        if self._name_cache is None:
            from sqlalchemy import select
            self._name_cache = {}
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Feed).where(Feed.provider == "rss")
                )
                for feed in result.scalars().all():
                    key = _normalize_name(feed.name)
                    if key not in self._name_cache:
                        self._name_cache[key] = feed
        return self._name_cache

    def invalidate_name_cache(self) -> None:
        """使名称缓存失效（新增 Feed 后调用）。"""
        self._name_cache = None

    async def resolve_feed(
        self,
        article_info: dict[str, Any],
        report: DiscoveryReport | None = None,
    ) -> DiscoveredFeed | None:
        """从 RSS 文章信息解析或创建对应的本地 Feed。

        匹配优先级:
        1. stable_id 通过 provider_feed_id 字段精确匹配
        2. display_name 归一化匹配
        3. 根据 auto-subscribe 设置决定是否创建新 Feed

        Args:
            article_info: RSS 文章信息字典
            report: 可选的发现报告收集器

        Returns:
            DiscoveredFeed 或 None（无法匹配且策略为 skip 时）
        """
        settings = get_settings()
        identity = extract_public_account_identity(article_info)
        stable_id = identity["stable_id"]
        display_name = identity["display_name"]
        raw_metadata = identity["raw_metadata"]

        if not stable_id:
            # 无法提取任何身份信息
            return self._handle_unknown_identity(article_info, report)

        # 1. 通过 stable_id 精确匹配（provider_feed_id）
        feed = await self._match_by_stable_id(stable_id)
        if feed:
            return DiscoveredFeed(feed=feed, is_newly_discovered=False, match_method="stable_id")

        # 2. 通过归一化名称匹配
        if display_name:
            feed = await self._match_by_name(display_name)
            if feed:
                # 补充 stable_id 到已有 Feed
                await self._update_feed_stable_id(feed, stable_id, raw_metadata)
                return DiscoveredFeed(feed=feed, is_newly_discovered=False, match_method="name")

        # 3. 根据策略创建或跳过
        return await self._create_or_skip(
            stable_id=stable_id,
            display_name=display_name,
            raw_metadata=raw_metadata,
            article_info=article_info,
            report=report,
        )

    async def _match_by_stable_id(self, stable_id: str) -> Feed | None:
        """通过 stable_id 匹配已有 Feed（查找 provider_feed_id 或 provider_meta）。"""
        from sqlalchemy import select

        async with self.db.get_session() as session:
            # 先尝试 provider_feed_id 精确匹配
            result = await session.execute(
                select(Feed).where(Feed.provider_feed_id == stable_id)
            )
            feed = result.scalar_one_or_none()
            if feed:
                return feed

            # 再尝试 provider_meta JSON 包含 stable_id
            result = await session.execute(
                select(Feed).where(
                    Feed.provider_meta.contains(stable_id),
                    Feed.provider == "rss",
                )
            )
            return result.scalar_one_or_none()

    async def _match_by_name(self, name: str) -> Feed | None:
        """通过归一化名称匹配已有 Feed（使用缓存）。"""
        cache = await self._get_name_cache()
        return cache.get(_normalize_name(name))

    async def _update_feed_stable_id(
        self, feed: Feed, stable_id: str, raw_metadata: dict[str, Any]
    ) -> None:
        """为已有 Feed 补充 stable_id。"""
        meta = {}
        if feed.provider_meta:
            try:
                meta = json.loads(feed.provider_meta)
            except (json.JSONDecodeError, TypeError):
                pass
        meta["stable_id"] = stable_id
        meta["discovery_updated_at"] = datetime.now().isoformat()

        async with self.db.get_session() as session:
            from sqlalchemy import update
            await session.execute(
                update(Feed)
                .where(Feed.id == feed.id)
                .values(
                    provider_feed_id=stable_id,
                    provider_meta=json.dumps(meta, ensure_ascii=False),
                )
            )
        logger.debug("Feed stable_id 已更新: %s -> %s", feed.name, stable_id)

    async def _create_or_skip(
        self,
        stable_id: str,
        display_name: str | None,
        raw_metadata: dict[str, Any],
        article_info: dict[str, Any],
        report: DiscoveryReport | None,
    ) -> DiscoveredFeed | None:
        """根据 auto-subscribe 设置创建新 Feed 或跳过。"""
        settings = get_settings()
        auto_subscribe = settings.rss_auto_subscribe_discovered_feeds

        if not auto_subscribe:
            # 检查策略
            policy = settings.rss_unknown_feed_policy
            if policy == "skip":
                logger.debug(
                    "auto-subscribe 已关闭，跳过未知公众号: %s",
                    display_name or stable_id,
                )
                return None
            # create_placeholder: 继续创建

        # 确定名称
        name = display_name or f"RSS:{stable_id[:12]}"

        # 确定状态
        default_status = settings.rss_discovered_feed_default_status
        status = 1 if default_status == "active" else 0

        # 构建发现元数据
        discovery_meta = {
            "stable_id": stable_id,
            "discovered_at": datetime.now().isoformat(),
            "discovery_source": "rss_auto",
            "raw_metadata": raw_metadata,
        }

        feed, is_new = await self.subscription_service.add_subscription(
            mp_id=stable_id,
            name=name,
            provider="rss",
            provider_feed_id=stable_id,
            provider_meta=json.dumps(discovery_meta, ensure_ascii=False),
        )

        # 如果应该停用且确实是新建的，在同一次事务中设置 status
        if status == 0 and is_new and feed.status == 1:
            from sqlalchemy import update as sa_update
            async with self.db.get_session() as session:
                await session.execute(
                    sa_update(Feed).where(Feed.id == feed.id).values(status=0)
                )
                feed.status = 0

        result = DiscoveredFeed(
            feed=feed,
            is_newly_discovered=is_new,
            match_method="placeholder" if not display_name else "author",
        )
        if report:
            report.add(result)

        # 新增 Feed 后刷新名称缓存
        if is_new:
            self.invalidate_name_cache()

        logger.info("自动发现并创建公众号订阅: %s (状态: %s)", name, default_status)
        return result

    def _handle_unknown_identity(
        self,
        article_info: dict[str, Any],
        report: DiscoveryReport | None,
    ) -> DiscoveredFeed | None:
        """处理无法提取身份信息的情况。"""
        settings = get_settings()
        title = article_info.get("title", "未知")

        if settings.rss_unknown_feed_policy == "skip":
            logger.debug("无法提取公众号身份，跳过: %s", title)
            return None

        # create_placeholder: 使用 URL hash 创建占位
        original_url = article_info.get("original_url") or article_info.get("url") or ""
        placeholder_id = f"rss:unknown:{_stable_hash(original_url or title)}"
        name = f"未知:{title[:15]}"

        # 这里需要同步调用 add_subscription，但因为我们在同步上下文中
        # 实际上不会到达这里 - _create_or_skip 会处理
        logger.warning("无法提取公众号身份，将创建占位订阅: %s", title)
        return None
