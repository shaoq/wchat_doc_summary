"""Wechat2RSS 文章列表 Provider。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from config.settings import get_settings
from src.api.article import fetch_article_content, parse_article_html
from src.api.providers.base import (
    ArticleListProvider,
    ProviderArticle,
    ProviderArticlePage,
    ProviderSubscription,
)

logger = logging.getLogger(__name__)

_FEED_ID_RE = re.compile(r"/feed/([^/.]+)\.(?:xml|json)$")


class Wechat2RSSProviderError(Exception):
    """Wechat2RSS 调用错误。"""


class Wechat2RSSProvider(ArticleListProvider):
    """基于 Wechat2RSS feed/json 接口的 Provider 实现。"""

    name = "wechat2rss"
    requires_auth = False

    def __init__(self, base_url: str | None = None, token: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.wechat2rss_base_url).rstrip("/")
        self.token = token or settings.wechat2rss_token
        self.timeout = settings.request_timeout

    def _with_token(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(params or {})
        if self.token:
            payload.setdefault("k", self.token)
        return payload

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                params=self._with_token(params),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise Wechat2RSSProviderError("Wechat2RSS 返回格式错误")
            return data

    async def _request_text(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                params=self._with_token(params),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.text.strip()

    def _extract_feed_id(self, payload: str) -> str | None:
        match = _FEED_ID_RE.search(payload)
        if match:
            return match.group(1)
        if payload.isdigit():
            return payload
        return None

    async def _fetch_feed_json(self, feed_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/feed/{feed_id}.json")

    def _normalize_feed_items(
        self,
        payload: dict[str, Any],
        *,
        page: int,
        page_size: int,
    ) -> ProviderArticlePage:
        items = payload.get("items", [])
        if not isinstance(items, list):
            items = []
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        sliced = items[start:end]

        normalized: list[ProviderArticle] = []
        for item in sliced:
            if not isinstance(item, dict):
                continue
            normalized.append(
                ProviderArticle(
                    title=item.get("title", "无标题"),
                    provider=self.name,
                    external_id=str(item.get("id") or item.get("guid") or item.get("url") or ""),
                    article_id=None,
                    url=item.get("url") or item.get("external_url"),
                    publish_time=item.get("date_published") or item.get("created"),
                    cover=item.get("image"),
                    summary=item.get("summary"),
                    content_html=item.get("content_html") or item.get("content"),
                    raw=item,
                )
            )

        return ProviderArticlePage(
            articles=normalized,
            page=page,
            page_size=page_size,
            total=len(items),
        )

    async def get_subscription_from_article(self, article_url: str) -> ProviderSubscription:
        payload = await self._request_text("GET", "/addurl", params={"url": article_url})
        feed_id = self._extract_feed_id(payload)
        if not feed_id:
            raise Wechat2RSSProviderError(f"无法解析 Wechat2RSS 订阅标识: {payload}")

        feed_payload = await self._fetch_feed_json(feed_id)
        html = await fetch_article_content(article_url)
        parsed = parse_article_html(html)
        feed_title = feed_payload.get("title") if isinstance(feed_payload, dict) else None
        name = feed_title or parsed.get("author") or feed_id
        cover = ""
        if isinstance(feed_payload, dict):
            cover = str(feed_payload.get("icon") or "")
        if not cover:
            cover = parsed.get("cover") or ""

        return ProviderSubscription(
            mp_id=feed_id,
            name=name,
            intro="",
            cover=cover,
            provider=self.name,
            provider_feed_id=feed_id,
            provider_meta=json.dumps(
                {
                    "feed_url": payload,
                    "article_url": article_url,
                },
                ensure_ascii=False,
            ),
        )

    async def get_articles(
        self,
        mp_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> ProviderArticlePage:
        payload = await self._fetch_feed_json(mp_id)
        return self._normalize_feed_items(payload, page=page, page_size=page_size)
