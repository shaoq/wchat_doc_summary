"""通用 RSS 文章列表 Provider - 支持标准 RSS/Atom Feed 及微信 RSS SaaS。"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import feedparser
import httpx

from config.settings import get_settings
from src.api.providers.base import (
    ArticleListProvider,
    ProviderArticle,
    ProviderArticlePage,
    ProviderSubscription,
)

logger = logging.getLogger(__name__)

# 用于脱敏的敏感查询参数名（不区分大小写）
_SENSITIVE_PARAMS = frozenset({
    "key", "token", "k", "api_key", "apikey", "secret", "auth",
    "access_token",
})


class RSSProviderError(Exception):
    """RSS Provider 调用错误。"""


def redact_url(url: str) -> str:
    """脱敏 URL 中的敏感查询参数值。"""
    parsed = urlparse(url)
    if not parsed.query:
        return url

    params = parse_qs(parsed.query, keep_blank_values=True)
    redacted: dict[str, list[str]] = {}
    for key, values in params.items():
        if key.lower() in _SENSITIVE_PARAMS:
            redacted[key] = ["***"]
        else:
            redacted[key] = values

    new_query = urlencode(redacted, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _parse_time(value: Any) -> datetime | str | None:
    """解析 feedparser 时间结构或字符串为 datetime。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return value
    # feedparser 的 FeedParserDict 时间结构
    if hasattr(value, "_parsed") or isinstance(value, dict):
        # feedparser 解析后的 time_value 有 parsed 属性
        try:
            import time as _time

            parsed_tuple = value.get("parsed") if isinstance(value, dict) else None
            if parsed_tuple and len(parsed_tuple) >= 9:
                return datetime(*parsed_tuple[:6])
        except (TypeError, ValueError):
            pass
    return None


class RSSProvider(ArticleListProvider):
    """通用 RSS 文章列表 Provider。

    支持标准 RSS 2.0 / Atom Feed，专为微信 RSS SaaS 场景设计：
    - 全局 API Key 从 settings 获取，不存储在源记录中
    - 支持单个聚合源（如 `全部`）和多个分类源
    - 自动脱敏诊断输出中的敏感 URL 参数
    """

    name = "rss"
    requires_auth = False

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.wechat_rss_api_key
        self.timeout = settings.request_timeout

    def _apply_api_key(self, url: str) -> str:
        """如果 URL 需要认证且有全局 API Key，附加到查询参数。"""
        if not self.api_key:
            return url
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if "key" not in params and "k" not in params and "token" not in params:
            params["key"] = [self.api_key]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    async def _fetch_feed(self, feed_url: str) -> feedparser.FeedParserDict:
        """异步抓取并解析 RSS/Atom Feed。"""
        url = self._apply_api_key(feed_url)
        logger.debug("RSS fetch: %s", redact_url(feed_url))

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()

        feed = feedparser.parse(response.text)
        if feed.bozo and not feed.entries:
            raise RSSProviderError(f"RSS Feed 解析失败: {feed.bozo_exception}")
        return feed

    def _normalize_entry(self, entry: Any) -> ProviderArticle:
        """将 RSS/Atom 条目标准化为 ProviderArticle。"""
        # 提取 stable identity
        external_id = getattr(entry, "id", None) or ""
        if not external_id:
            external_id = getattr(entry, "guid", "") or ""

        # 提取 URL
        url = getattr(entry, "link", None) or ""
        if not url:
            links = getattr(entry, "links", [])
            for link in links:
                if getattr(link, "rel", "") == "alternate" or not getattr(link, "rel", ""):
                    url = getattr(link, "href", "")
                    break

        # 提取标题
        title = getattr(entry, "title", "") or "无标题"

        # 提取发布时间
        publish_time = _parse_time(getattr(entry, "published_parsed", None))
        if publish_time is None:
            publish_time = _parse_time(getattr(entry, "updated_parsed", None))
        if publish_time is None:
            publish_time = getattr(entry, "published", None) or getattr(entry, "updated", None)

        # 提取摘要
        summary = getattr(entry, "summary", None) or getattr(entry, "description", None)

        # 提取 HTML 内容
        content_html = None
        content_items = getattr(entry, "content", None)
        if content_items:
            for item in content_items:
                content_html = getattr(item, "value", None)
                if content_html:
                    break
        if not content_html:
            # 某些 RSS 使用 content:encoded
            content_html = getattr(entry, "content", [{}])
            if isinstance(content_html, list) and content_html:
                content_html = content_html[0].get("value") if isinstance(content_html[0], dict) else None
            if not content_html:
                content_html = summary

        # 提取封面
        cover = None
        media_content = getattr(entry, "media_content", [])
        if media_content:
            cover = media_content[0].get("url") if isinstance(media_content[0], dict) else None
        if not cover:
            enclosure = getattr(entry, "enclosures", [])
            if enclosure:
                for enc in enclosure:
                    enc_type = enc.get("type", "")
                    if enc_type.startswith("image/"):
                        cover = enc.get("href") or enc.get("url")
                        break

        # 构建 raw dict（排除不可序列化的 parsed 元组）
        raw: dict[str, Any] = {}
        for attr in ("title", "link", "id", "guid", "summary", "published", "updated", "author"):
            val = getattr(entry, attr, None)
            if val is not None:
                raw[attr] = str(val)

        return ProviderArticle(
            title=title,
            provider=self.name,
            external_id=str(external_id) if external_id else None,
            article_id=None,
            url=url or None,
            publish_time=publish_time,
            cover=cover,
            summary=summary,
            content_html=content_html,
            raw=raw,
        )

    def _normalize_feed(
        self,
        feed: feedparser.FeedParserDict,
        *,
        page: int,
        page_size: int,
    ) -> ProviderArticlePage:
        """将完整 feed 解析结果标准化为分页结果。"""
        entries = feed.entries or []
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        sliced = entries[start:end]

        articles = [self._normalize_entry(entry) for entry in sliced]
        return ProviderArticlePage(
            articles=articles,
            page=page,
            page_size=page_size,
            total=len(entries),
        )

    async def get_subscription_from_article(self, article_url: str) -> ProviderSubscription:
        """RSS provider 不支持从单篇文章推断订阅。"""
        raise RSSProviderError(
            "RSS Provider 不支持从文章 URL 自动解析订阅。请通过 `wchat source add` 手动添加 RSS 源。"
        )

    async def get_articles(
        self,
        mp_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> ProviderArticlePage:
        """通过 mp_id（实际为 RSS 源 feed_url）获取文章列表。"""
        # mp_id 在 RSS provider 上下文中作为 feed URL 使用
        feed_url = mp_id
        feed = await self._fetch_feed(feed_url)
        return self._normalize_feed(feed, page=page, page_size=page_size)
