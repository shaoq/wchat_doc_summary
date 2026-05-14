"""RSS Provider 单元测试 - 覆盖 item 标准化、URL 路由、聚合源行为、内容提取、API Key、URL 脱敏。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.providers.rss_provider import RSSProvider, RSSProviderError, redact_url


class TestRedactURL:
    """URL 脱敏测试。"""

    def test_redacts_key_param(self) -> None:
        result = redact_url("https://example.com/feed?key=secret123&cat=tech")
        assert "secret123" not in result
        assert "key=" in result
        assert "cat=tech" in result

    def test_redacts_token_param(self) -> None:
        result = redact_url("https://example.com/feed?token=abc&name=test")
        assert "abc" not in result
        assert "token=" in result
        assert "name=test" in result

    def test_redacts_k_param(self) -> None:
        result = redact_url("https://example.com/feed?k=mykey")
        assert "mykey" not in result

    def test_no_redaction_when_no_sensitive_params(self) -> None:
        url = "https://example.com/feed?cat=tech&page=1"
        assert redact_url(url) == url

    def test_no_redaction_when_no_query(self) -> None:
        url = "https://example.com/feed"
        assert redact_url(url) == url

    def test_redacts_multiple_sensitive_params(self) -> None:
        result = redact_url("https://example.com?key=secret&token=abc&name=ok")
        assert "secret" not in result
        assert "abc" not in result
        assert "name=ok" in result


class TestRSSProviderFactory:
    """Provider 工厂注册测试。"""

    def test_create_rss_provider(self) -> None:
        from src.api.providers import create_article_list_provider

        client = MagicMock()
        with patch("src.api.providers.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                article_list_provider="rss",
                wechat_rss_api_key="test_key",
                request_timeout=30,
            )
            with patch("src.api.providers.rss_provider.get_settings") as mock_prov_settings:
                mock_prov_settings.return_value = MagicMock(
                    wechat_rss_api_key="test_key",
                    request_timeout=30,
                )
                provider = create_article_list_provider(client)

        assert isinstance(provider, RSSProvider)
        assert provider.name == "rss"
        assert provider.api_key == "test_key"

    def test_rss_provider_requires_no_auth(self) -> None:
        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None,
                request_timeout=30,
            )
            provider = RSSProvider()
        assert provider.requires_auth is False


class TestRSSProviderGetArticles:
    """RSS 文章列表获取测试。"""

    @pytest.mark.asyncio
    async def test_fetch_and_normalize_rss_items(self) -> None:
        """测试 RSS feed 解析和 item 标准化。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>测试 Feed</title>
            <item>
              <title>文章1</title>
              <link>https://mp.weixin.qq.com/s/test1</link>
              <guid>guid-001</guid>
              <pubDate>Mon, 13 May 2026 10:00:00 +0800</pubDate>
              <description>摘要内容1</description>
              <content:encoded><![CDATA[<div>正文1</div>]]></content:encoded>
            </item>
            <item>
              <title>文章2</title>
              <link>https://mp.weixin.qq.com/s/test2</link>
              <guid>guid-002</guid>
              <pubDate>Mon, 12 May 2026 08:00:00 +0800</pubDate>
              <description>摘要内容2</description>
            </item>
          </channel>
        </rss>"""

        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None,
                request_timeout=30,
            )
            provider = RSSProvider()

        with patch.object(provider, "_fetch_feed") as mock_fetch:
            import feedparser
            mock_fetch.return_value = feedparser.parse(rss_xml)

            page = await provider.get_articles("https://example.com/feed", page=1, page_size=10)

        assert page.total == 2
        assert len(page.articles) == 2

        art1 = page.articles[0]
        assert art1.title == "文章1"
        assert art1.url == "https://mp.weixin.qq.com/s/test1"
        assert art1.external_id == "guid-001"
        assert art1.provider == "rss"
        assert art1.summary == "摘要内容1"

    @pytest.mark.asyncio
    async def test_single_aggregate_source(self) -> None:
        """测试单个聚合源（如 `全部`）行为。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>全部</title>
            <item>
              <title>聚合文章</title>
              <link>https://mp.weixin.qq.com/s/agg1</link>
              <guid>agg-001</guid>
            </item>
          </channel>
        </rss>"""

        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None, request_timeout=30,
            )
            provider = RSSProvider()

        with patch.object(provider, "_fetch_feed") as mock_fetch:
            import feedparser
            mock_fetch.return_value = feedparser.parse(rss_xml)
            page = await provider.get_articles("https://example.com/all", page=1, page_size=50)

        assert page.total == 1
        assert page.articles[0].title == "聚合文章"

    @pytest.mark.asyncio
    async def test_pagination(self) -> None:
        """测试客户端分页。"""
        items = "".join(
            f"<item><title>文章{i}</title><link>https://example.com/{i}</link>"
            f"<guid>guid-{i}</guid></item>"
            for i in range(5)
        )
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>测试</title>{items}</channel></rss>"""

        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None, request_timeout=30,
            )
            provider = RSSProvider()

        with patch.object(provider, "_fetch_feed") as mock_fetch:
            import feedparser
            mock_fetch.return_value = feedparser.parse(rss_xml)
            page = await provider.get_articles("test", page=2, page_size=2)

        assert page.total == 5
        assert len(page.articles) == 2
        assert page.articles[0].title == "文章2"


class TestRSSProviderAPIKey:
    """API Key 使用测试。"""

    def test_apply_api_key_adds_key_param(self) -> None:
        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key="my-secret-key",
                request_timeout=30,
            )
            provider = RSSProvider()

        result = provider._apply_api_key("https://example.com/feed?cat=tech")
        assert "key=my-secret-key" in result
        assert "cat=tech" in result

    def test_apply_api_key_skips_if_already_present(self) -> None:
        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key="new-key",
                request_timeout=30,
            )
            provider = RSSProvider()

        result = provider._apply_api_key("https://example.com/feed?key=existing")
        assert "key=existing" in result
        assert "new-key" not in result

    def test_apply_api_key_no_key_configured(self) -> None:
        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None,
                request_timeout=30,
            )
            provider = RSSProvider()

        result = provider._apply_api_key("https://example.com/feed")
        assert "key=" not in result


class TestRSSProviderSubscription:
    """订阅解析测试。"""

    @pytest.mark.asyncio
    async def test_get_subscription_raises_error(self) -> None:
        """RSS provider 不支持从文章 URL 解析订阅。"""
        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None, request_timeout=30,
            )
            provider = RSSProvider()

        with pytest.raises(RSSProviderError, match="不支持从文章 URL"):
            await provider.get_subscription_from_article("https://mp.weixin.qq.com/s/test")


class TestRSSProviderContentExtraction:
    """内容提取测试。"""

    @pytest.mark.asyncio
    async def test_extracts_html_content(self) -> None:
        """测试从 RSS item 提取 HTML 内容。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel><title>测试</title>
            <item>
              <title>带内容文章</title>
              <link>https://mp.weixin.qq.com/s/content1</link>
              <guid>content-001</guid>
              <content:encoded><![CDATA[<div><p>完整 HTML 内容</p></div>]]></content:encoded>
            </item>
          </channel>
        </rss>"""

        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None, request_timeout=30,
            )
            provider = RSSProvider()

        with patch.object(provider, "_fetch_feed") as mock_fetch:
            import feedparser
            mock_fetch.return_value = feedparser.parse(rss_xml)
            page = await provider.get_articles("test", page=1, page_size=10)

        art = page.articles[0]
        assert art.content_html is not None
        assert "完整 HTML 内容" in art.content_html

    @pytest.mark.asyncio
    async def test_falls_back_to_summary(self) -> None:
        """测试无 content_html 时回退到 summary。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel><title>测试</title>
            <item>
              <title>仅摘要</title>
              <link>https://mp.weixin.qq.com/s/summary1</link>
              <guid>summary-001</guid>
              <description>这是摘要内容</description>
            </item>
          </channel>
        </rss>"""

        with patch("src.api.providers.rss_provider.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                wechat_rss_api_key=None, request_timeout=30,
            )
            provider = RSSProvider()

        with patch.object(provider, "_fetch_feed") as mock_fetch:
            import feedparser
            mock_fetch.return_value = feedparser.parse(rss_xml)
            page = await provider.get_articles("test", page=1, page_size=10)

        art = page.articles[0]
        assert art.summary == "这是摘要内容"
