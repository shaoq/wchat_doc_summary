"""API 模块 - 处理外部 API 调用。

提供微信读书代理 API 和微信公众号文章抓取功能。
"""

from src.api.article import (
    ArticleFetchError,
    extract_images,
    fetch_article_content,
    parse_article_html,
)
from src.api.providers import (
    ArticleListProvider,
    ProviderArticle,
    ProviderArticlePage,
    ProviderSubscription,
    Wechat2RSSProvider,
    Wechat2RSSProviderError,
    WeReadArticleProvider,
    create_article_list_provider,
)
from src.api.weread import RateLimitError, WeReadAPIError, WeReadClient

__all__ = [
    # 微信读书 API
    "WeReadClient",
    "WeReadAPIError",
    "RateLimitError",
    # 文章抓取
    "fetch_article_content",
    "parse_article_html",
    "extract_images",
    "ArticleFetchError",
    # 文章列表 Provider
    "ArticleListProvider",
    "ProviderArticle",
    "ProviderArticlePage",
    "ProviderSubscription",
    "Wechat2RSSProvider",
    "Wechat2RSSProviderError",
    "WeReadArticleProvider",
    "create_article_list_provider",
]
