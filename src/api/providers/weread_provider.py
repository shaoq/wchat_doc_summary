"""WeRead 文章列表 Provider 适配层。"""

from __future__ import annotations

from typing import Any

from src.api.providers.base import (
    ArticleListProvider,
    ProviderArticle,
    ProviderArticlePage,
    ProviderSubscription,
)
from src.api.weread import WeReadClient


class WeReadArticleProvider(ArticleListProvider):
    """基于现有 WeRead API 的 Provider 实现。"""

    name = "weread"
    requires_auth = True
    supports_narrow_retry = True

    def __init__(self, client: WeReadClient):
        self.client = client

    async def get_subscription_from_article(self, article_url: str) -> ProviderSubscription:
        info = await self.client.get_mp_info(article_url)
        mp_id = str(info.get("mp_id") or "")
        return ProviderSubscription(
            mp_id=mp_id,
            name=info.get("name") or mp_id,
            intro=info.get("intro", ""),
            cover=info.get("cover", ""),
            provider=self.name,
            provider_feed_id=mp_id,
        )

    async def get_articles(
        self,
        mp_id: str,
        page: int = 1,
        page_size: int = 50,
        **kwargs: Any,
    ) -> ProviderArticlePage:
        response = await self.client.get_articles(
            mp_id,
            page=page,
            page_size=page_size,
            **kwargs,
        )
        items = response.get("articles", []) if isinstance(response, dict) else response
        normalized = [
            ProviderArticle(
                title=item.get("title", "无标题"),
                provider=self.name,
                external_id=str(item.get("id") or item.get("article_id") or ""),
                article_id=item.get("id") or item.get("article_id"),
                url=f"https://mp.weixin.qq.com/s/{item.get('id') or item.get('article_id')}"
                if item.get("id") or item.get("article_id")
                else None,
                publish_time=item.get("publish_time") or item.get("publishTime"),
                cover=item.get("cover"),
                raw=item,
            )
            for item in items
            if isinstance(item, dict)
        ]
        resolved_page = response.get("page", page) if isinstance(response, dict) else page
        resolved_page_size = (
            (response.get("page_size") or response.get("pageSize") or page_size)
            if isinstance(response, dict)
            else page_size
        )
        resolved_total = response.get("total") if isinstance(response, dict) else len(normalized)

        return ProviderArticlePage(
            articles=normalized,
            page=resolved_page,
            page_size=resolved_page_size,
            total=resolved_total,
        )
