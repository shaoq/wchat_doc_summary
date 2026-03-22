"""API 模块 - 处理外部 API 调用。

提供微信读书代理 API 和微信公众号文章抓取功能。
"""

from src.api.article import (
    ArticleFetchError,
    extract_images,
    fetch_article_content,
    parse_article_html,
)
from src.api.weread import WeReadAPIError, WeReadClient

__all__ = [
    # 微信读书 API
    "WeReadClient",
    "WeReadAPIError",
    # 文章抓取
    "fetch_article_content",
    "parse_article_html",
    "extract_images",
    "ArticleFetchError",
]
