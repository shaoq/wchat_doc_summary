"""文章列表 Provider 抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ProviderArticle:
    """标准化后的文章列表项。"""

    title: str
    provider: str
    external_id: str | None = None
    article_id: str | None = None
    url: str | None = None
    publish_time: str | int | datetime | None = None
    cover: str | None = None
    summary: str | None = None
    content_html: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_article_info(self) -> dict[str, Any]:
        """转换为抓取服务兼容的字典。"""
        return {
            "id": self.article_id,
            "article_id": self.article_id,
            "external_id": self.external_id,
            "provider": self.provider,
            "provider_item_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "original_url": self.url,
            "publish_time": self.publish_time,
            "cover": self.cover,
            "summary": self.summary,
            "content_html": self.content_html,
            "raw": self.raw,
        }


@dataclass(slots=True)
class ProviderArticlePage:
    """标准化后的文章列表分页结果。"""

    articles: list[ProviderArticle]
    page: int
    page_size: int
    total: int | None = None


@dataclass(slots=True)
class ProviderSubscription:
    """标准化后的订阅解析结果。"""

    mp_id: str
    name: str
    provider: str
    intro: str = ""
    cover: str = ""
    provider_feed_id: str | None = None
    provider_meta: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为订阅服务兼容的字典。"""
        return {
            "mp_id": self.mp_id,
            "name": self.name,
            "intro": self.intro,
            "cover": self.cover,
            "provider": self.provider,
            "provider_feed_id": self.provider_feed_id or self.mp_id,
            "provider_meta": self.provider_meta,
        }


class ArticleListProvider(ABC):
    """文章列表 Provider 抽象基类。"""

    name = "unknown"
    requires_auth = False
    supports_narrow_retry = False

    @abstractmethod
    async def get_subscription_from_article(self, article_url: str) -> ProviderSubscription:
        """根据文章 URL 解析订阅信息。"""

    @abstractmethod
    async def get_articles(
        self,
        mp_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> ProviderArticlePage:
        """获取公众号文章列表。"""
