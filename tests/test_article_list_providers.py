"""文章列表 Provider 测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.providers import (
    WeReadArticleProvider,
    Wechat2RSSProvider,
    create_article_list_provider,
)


class TestProviderFactory:
    """Provider 工厂测试。"""

    def test_create_weread_provider(self) -> None:
        """测试默认创建 weread provider。"""
        client = MagicMock()
        with patch("src.api.providers.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(article_list_provider="weread")
            provider = create_article_list_provider(client)

        assert isinstance(provider, WeReadArticleProvider)

    def test_create_wechat2rss_provider(self) -> None:
        """测试按配置创建 wechat2rss provider。"""
        client = MagicMock()
        with patch("src.api.providers.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                article_list_provider="wechat2rss",
                wechat2rss_base_url="https://wechat2rss.test",
                wechat2rss_token="token",
                request_timeout=30,
            )
            provider = create_article_list_provider(client)

        assert isinstance(provider, Wechat2RSSProvider)


class TestWechat2RSSProvider:
    """Wechat2RSS Provider 测试。"""

    @pytest.mark.asyncio
    async def test_get_articles_maps_feed_json(self) -> None:
        """测试 feed json 能映射为标准文章项。"""
        with patch("src.api.providers.wechat2rss.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat2rss_base_url="https://wechat2rss.test",
                wechat2rss_token="token",
                request_timeout=30,
            )
            provider = Wechat2RSSProvider()

        with patch.object(
            provider,
            "_fetch_feed_json",
            new=AsyncMock(
                return_value={
                    "title": "测试 feed",
                    "items": [
                        {
                            "id": "item_1",
                            "url": "https://mp.weixin.qq.com/s/test1",
                            "title": "文章1",
                            "date_published": "2026-03-31T10:00:00+08:00",
                            "content_html": "<div>正文1</div>",
                            "image": "https://example.com/cover1.jpg",
                        }
                    ],
                }
            ),
        ):
            page = await provider.get_articles("123456", page=1, page_size=10)

        assert page.total == 1
        assert len(page.articles) == 1
        article = page.articles[0]
        assert article.provider == "wechat2rss"
        assert article.url == "https://mp.weixin.qq.com/s/test1"
        assert article.content_html == "<div>正文1</div>"

    @pytest.mark.asyncio
    async def test_get_subscription_from_article_uses_addurl_and_feed(self) -> None:
        """测试从文章 URL 解析订阅信息。"""
        with patch("src.api.providers.wechat2rss.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat2rss_base_url="https://wechat2rss.test",
                wechat2rss_token="token",
                request_timeout=30,
            )
            provider = Wechat2RSSProvider()

        with patch.object(
            provider,
            "_request_text",
            new=AsyncMock(return_value="https://wechat2rss.test/feed/3008522239.xml"),
        ):
            with patch.object(
                provider,
                "_fetch_feed_json",
                new=AsyncMock(return_value={"title": "e公司", "icon": "https://example.com/icon.jpg"}),
            ):
                with patch(
                    "src.api.providers.wechat2rss.fetch_article_content",
                    new=AsyncMock(return_value="<html></html>"),
                ):
                    with patch(
                        "src.api.providers.wechat2rss.parse_article_html",
                        return_value={"author": "e公司", "cover": "https://example.com/cover.jpg"},
                    ):
                        subscription = await provider.get_subscription_from_article(
                            "https://mp.weixin.qq.com/s/test"
                        )

        assert subscription.mp_id == "3008522239"
        assert subscription.name == "e公司"
        assert subscription.provider == "wechat2rss"
        assert subscription.provider_feed_id == "3008522239"
