"""RSS URL 归属服务 - 基于 URL 的公众号身份解析与缓存。

实现分层归属解析：
1. 缓存优先：通过已有文章 URL、身份映射查找
2. 发现服务：使用 FeedDiscoveryService 进行身份匹配
3. 订阅兼容回退：对未知公众号通过 weread/wechat2rss provider 解析
4. 持久缓存：保存解析结果避免重复调用
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import or_, select

from config.settings import get_settings
from src.api.providers import create_article_list_provider
from src.api.weread import WeReadClient
from src.models.schema import Article, Feed
from src.api.providers.rss_provider import redact_url
from src.services.feed_discovery import DiscoveredFeed, DiscoveryReport, FeedDiscoveryService
from src.services.subscription import SubscriptionService
from src.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """RSS 归属解析结果。"""

    feed: Feed
    resolution_method: str  # existing_article | cached_identity | discovered | subscribe_resolved
    is_newly_discovered: bool = False
    was_subscribe_resolved: bool = False
    display_name: str | None = None


@dataclass
class AttributionDiagnostics:
    """RSS 归属解析诊断信息。"""

    total_items: int = 0
    cached_matches: int = 0
    discovered_matches: int = 0
    subscribe_resolved: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.cached_matches:
            lines.append(f"  缓存匹配: {self.cached_matches} 篇")
        if self.discovered_matches:
            lines.append(f"  已知公众号匹配: {self.discovered_matches} 篇")
        if self.subscribe_resolved:
            lines.append(f"  新发现（URL 解析）: {self.subscribe_resolved} 篇")
        if self.skipped:
            lines.append(f"  跳过: {self.skipped} 篇")
        if self.failed:
            lines.append(f"  失败: {self.failed} 篇")
        return lines


class RSSAttributionService:
    """RSS URL 归属服务。

    在 RSS 文章导入前解析其所属公众号，优先使用本地缓存，
    仅对未知公众号调用订阅兼容的 URL 解析器。
    """

    def __init__(
        self,
        db: Database,
        subscription_service: SubscriptionService,
        weread_client: WeReadClient,
    ) -> None:
        self.db = db
        self.subscription_service = subscription_service
        self.weread_client = weread_client
        self._discovery_service = FeedDiscoveryService(db, subscription_service)
        self._identity_provider_cache: dict[str, Any] = {}

    def _get_identity_provider(self):
        """获取用于 URL 解析的身份 provider（非 RSS）。"""
        settings = get_settings()
        provider_name = settings.rss_identity_resolver_provider
        if provider_name not in self._identity_provider_cache:
            self._identity_provider_cache[provider_name] = create_article_list_provider(
                self.weread_client,
                provider_name=provider_name,
            )
        return self._identity_provider_cache[provider_name]

    async def attribute(
        self,
        article_info: dict[str, Any],
        report: DiscoveryReport | None = None,
        diagnostics: AttributionDiagnostics | None = None,
    ) -> AttributionResult | None:
        """解析 RSS 文章到公众号 Feed。

        分层解析：
        1. 通过已有文章 URL 查找
        2. 通过 FeedDiscoveryService 身份匹配
        3. 订阅兼容回退（仅对未知公众号）
        4. 缓存结果

        Args:
            article_info: RSS 文章信息字典
            report: 可选的发现报告
            diagnostics: 可选的诊断信息收集器

        Returns:
            AttributionResult 或 None（无法解析且策略为 skip 时）
        """
        if diagnostics is not None:
            diagnostics.total_items += 1

        original_url = article_info.get("original_url") or article_info.get("url") or ""
        title = article_info.get("title", "无标题")

        # ── Tier 1: 通过已有文章 URL 直接匹配 ──
        if original_url:
            result = await self._match_by_existing_article(original_url, article_info)
            if result is not None:
                if diagnostics is not None:
                    diagnostics.cached_matches += 1
                logger.debug("RSS 归属 - 已有文章匹配: %s", title)
                return result

        # ── Tier 2: 通过身份映射（biz, provider_feed_id 等）匹配 ──
        identity_result = await self._match_by_cached_identity(article_info)
        if identity_result is not None:
            if diagnostics is not None:
                diagnostics.cached_matches += 1
            logger.debug("RSS 归属 - 身份缓存匹配: %s", title)
            return identity_result

        # ── Tier 3: 通过 FeedDiscoveryService 标准匹配 ──
        discovery_result = await self._discovery_service.resolve_feed(article_info, report=None)
        if discovery_result is not None:
            if diagnostics is not None:
                diagnostics.discovered_matches += 1
            # 统一在这里调用 report.add（单一写入点）
            if report is not None and discovery_result.is_newly_discovered:
                report.add(DiscoveredFeed(
                    feed=discovery_result.feed,
                    is_newly_discovered=True,
                    match_method="discovered",
                ))
            return AttributionResult(
                feed=discovery_result.feed,
                resolution_method="discovered",
                is_newly_discovered=discovery_result.is_newly_discovered,
                was_subscribe_resolved=False,
                display_name=discovery_result.feed.name,
            )

        # ── Tier 4: 订阅兼容回退 ──
        if original_url and self._should_try_subscribe_resolve():
            result = await self._subscribe_compatible_resolve(original_url, article_info, diagnostics)
            if result is not None:
                if report is not None:
                    report.add(DiscoveredFeed(
                        feed=result.feed,
                        is_newly_discovered=result.is_newly_discovered,
                        match_method="subscribe_resolve",
                    ))
                return result

        # ── 无法解析 ──
        settings = get_settings()
        if settings.rss_unknown_feed_policy == "skip":
            if diagnostics is not None:
                diagnostics.skipped += 1
            logger.debug("RSS 归属 - 跳过（无法解析）: %s", title)
            return None

        # create_placeholder: 创建占位订阅
        if diagnostics is not None:
            diagnostics.failed += 1
        return None

    async def _match_by_existing_article(
        self,
        original_url: str,
        article_info: dict[str, Any],
    ) -> AttributionResult | None:
        """通过已有文章 URL 查找其所属 Feed。"""
        provider = article_info.get("provider", "rss")
        provider_item_id = article_info.get("provider_item_id") or article_info.get("external_id")

        async with self.db.get_session() as session:
            # 先按 URL 精确匹配
            result = await session.execute(
                select(Article).where(Article.original_url == original_url).limit(1)
            )
            existing = result.scalar_one_or_none()

            if existing is None and provider and provider_item_id:
                # 再按 (provider, provider_item_id) 匹配
                from sqlalchemy import and_
                result = await session.execute(
                    select(Article).where(
                        and_(
                            Article.provider == provider,
                            Article.provider_item_id == str(provider_item_id),
                        )
                    ).limit(1)
                )
                existing = result.scalar_one_or_none()

            if existing is not None and existing.feed_id:
                feed = await session.get(Feed, existing.feed_id)
                if feed is not None:
                    return AttributionResult(
                        feed=feed,
                        resolution_method="existing_article",
                        display_name=feed.name,
                    )

        return None

    async def _match_by_cached_identity(
        self,
        article_info: dict[str, Any],
    ) -> AttributionResult | None:
        """通过缓存的公众号身份映射查找 Feed。

        检查：
        1. URL 中的 __biz 参数 → Feed.provider_feed_id 或 provider_meta
        2. RSS 条目的 author/source → 名称匹配 + 验证 provider_feed_id
        """
        from src.services.feed_discovery import extract_public_account_identity

        identity = extract_public_account_identity(article_info)
        stable_id = identity.get("stable_id")
        display_name = identity.get("display_name")

        if not stable_id:
            return None

        async with self.db.get_session() as session:
            # 通过 provider_feed_id 精确匹配
            result = await session.execute(
                select(Feed).where(Feed.provider_feed_id == stable_id).limit(1)
            )
            feed = result.scalar_one_or_none()
            if feed is not None:
                return AttributionResult(
                    feed=feed,
                    resolution_method="cached_identity",
                    display_name=feed.name,
                )

            # 仅对 biz:xxx 类型的 stable_id 检查 provider_meta
            if stable_id.startswith("biz:"):
                result = await session.execute(
                    select(Feed).where(
                        Feed.provider_meta.contains(stable_id),
                    ).limit(1)
                )
                feed = result.scalar_one_or_none()
                if feed is not None:
                    return AttributionResult(
                        feed=feed,
                        resolution_method="cached_identity",
                        display_name=feed.name,
                    )

        return None

    def _should_try_subscribe_resolve(self) -> bool:
        """判断是否应尝试订阅兼容解析。"""
        settings = get_settings()
        return settings.rss_auto_subscribe_discovered_feeds

    async def _subscribe_compatible_resolve(
        self,
        original_url: str,
        article_info: dict[str, Any],
        diagnostics: AttributionDiagnostics | None = None,
    ) -> AttributionResult | None:
        """通过订阅兼容的 provider 从文章 URL 解析公众号。

        使用配置的身份解析 provider（weread 或 wechat2rss），
        不依赖全局 ARTICLE_LIST_PROVIDER=rss。
        """
        title = article_info.get("title", "无标题")
        logger.info("RSS 归属 - 尝试 URL 解析: %s -> %s", title, original_url)

        try:
            provider = self._get_identity_provider()
            subscription_info = await provider.get_subscription_from_article(original_url)
        except Exception as e:
            logger.warning("RSS 归属 - URL 解析失败: %s - %s", title, e)
            return None

        if not subscription_info or not subscription_info.mp_id:
            logger.debug("RSS 归属 - URL 解析无结果: %s", title)
            return None

        # 创建或更新订阅
        info_dict = subscription_info.to_dict()
        feed, is_new = await self.subscription_service.add_subscription(
            mp_id=info_dict["mp_id"],
            name=info_dict["name"],
            intro=info_dict.get("intro", ""),
            cover=info_dict.get("cover", ""),
            provider=info_dict.get("provider"),
            provider_feed_id=info_dict.get("provider_feed_id"),
            provider_meta=self._build_attribution_meta(article_info, info_dict),
        )

        if diagnostics is not None:
            diagnostics.subscribe_resolved += 1

        logger.info(
            "RSS 归属 - URL 解析成功: %s -> %s (%s)",
            title, feed.name, subscription_info.mp_id,
        )

        return AttributionResult(
            feed=feed,
            resolution_method="subscribe_resolved",
            is_newly_discovered=is_new,
            was_subscribe_resolved=True,
            display_name=feed.name,
        )

    def _build_attribution_meta(
        self,
        article_info: dict[str, Any],
        subscription_info: dict[str, Any],
    ) -> str:
        """构建归属元数据，用于缓存和追溯。"""
        original_url = article_info.get("original_url") or article_info.get("url") or ""
        raw = article_info.get("raw", {})

        # 提取 __biz 用于后续快速匹配
        biz_id: str | None = None
        if original_url and "__biz" in original_url:
            try:
                parsed = urlparse(original_url)
                params = parse_qs(parsed.query)
                biz_values = params.get("__biz", [])
                if biz_values and biz_values[0]:
                    biz_id = f"biz:{biz_values[0]}"
            except Exception:
                pass

        meta = {
            "discovered_at": datetime.now().isoformat(),
            "discovery_source": "rss_attribution",
            "identity_resolver": get_settings().rss_identity_resolver_provider,
            "original_url_sample": redact_url(original_url[:200]) if original_url else None,
            "resolved_mp_id": subscription_info.get("mp_id"),
            "resolved_name": subscription_info.get("name"),
        }
        if biz_id:
            meta["stable_id"] = biz_id
        if raw.get("author"):
            meta["rss_author"] = raw["author"]

        return json.dumps(meta, ensure_ascii=False)
