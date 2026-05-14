"""文章列表 Provider 工厂。"""

from __future__ import annotations

from config.settings import get_settings
from src.api.providers.base import ArticleListProvider
from src.api.providers.rss_provider import RSSProvider
from src.api.providers.wechat2rss import Wechat2RSSProvider
from src.api.providers.weread_provider import WeReadArticleProvider
from src.api.weread import WeReadClient


def create_article_list_provider(
    weread_client: WeReadClient,
    provider_name: str | None = None,
) -> ArticleListProvider:
    """根据配置创建文章列表 Provider。"""
    settings = get_settings()
    provider = provider_name or settings.article_list_provider
    if provider == "wechat2rss":
        return Wechat2RSSProvider()
    if provider == "rss":
        return RSSProvider()
    return WeReadArticleProvider(weread_client)
