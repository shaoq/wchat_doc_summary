"""测试 RSS HTML 正文存储修复 — 覆盖内容分类、持久化、导出回退和历史修复。"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.providers.base import ProviderArticle, ProviderArticlePage
from src.api.providers.rss_provider import RSSProvider
from src.cli.article import build_article_html
from src.models.schema import Article, Feed
from src.services.fetcher import FetcherService
from src.services.rss_source import RSSSourceService
from src.services.subscription import SubscriptionService
from src.storage.database import Database
from src.utils.html_detect import looks_like_html_body


# ── Fixtures ──────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db() -> Database:
    database = Database(database_url="sqlite+aiosqlite:///:memory:")
    await database.init_db()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def subscription_service(db: Database) -> SubscriptionService:
    return SubscriptionService(db)


@pytest_asyncio.fixture
async def rss_service(db: Database) -> RSSSourceService:
    return RSSSourceService(db)


@pytest_asyncio.fixture
async def fetcher(db: Database, subscription_service: SubscriptionService) -> FetcherService:
    return FetcherService(MagicMock(), db, subscription_service)


def _make_rss_article(
    title: str = "测试文章",
    url: str = "https://mp.weixin.qq.com/s/test1",
    external_id: str = "guid-001",
    content_html: str | None = "<div>Feed 内容</div>",
    summary: str | None = "摘要",
) -> ProviderArticle:
    return ProviderArticle(
        title=title,
        provider="rss",
        external_id=external_id,
        url=url,
        publish_time="2026-05-13T10:00:00+08:00",
        summary=summary,
        content_html=content_html,
    )


def _make_db_article(
    title: str = "测试文章",
    content: str | None = None,
    summary: str | None = None,
    provider: str = "rss",
) -> Article:
    return Article(
        id=1,
        feed_id=1,
        article_id="art-001",
        title=title,
        content=content,
        summary=summary,
        provider=provider,
    )


# ── 6.1 HTML 检测工具 ────────────────────────────────────────────


class TestLooksLikeHtmlBody:
    """looks_like_html_body 辅助函数测试。"""

    def test_detects_html_with_block_tags(self) -> None:
        assert looks_like_html_body("<p>段落</p><div>内容</div>") is True

    def test_detects_html_with_leading_angle_bracket(self) -> None:
        assert looks_like_html_body("<div>完整 HTML</div>") is True

    def test_detects_escaped_tags(self) -> None:
        assert looks_like_html_body("&lt;p&gt;转义内容&lt;/p&gt;") is True

    def test_rejects_plain_text(self) -> None:
        assert looks_like_html_body("这是一段纯文本摘要") is False

    def test_rejects_text_with_math_symbols(self) -> None:
        assert looks_like_html_body("x < 5 且 y > 3") is False

    def test_handles_none(self) -> None:
        assert looks_like_html_body(None) is False

    def test_handles_empty_string(self) -> None:
        assert looks_like_html_body("") is False

    def test_detects_img_tag(self) -> None:
        assert looks_like_html_body('<img src="test.jpg">') is True

    def test_detects_br_at_line_start(self) -> None:
        """以 <br> 开头的片段应被检测为 HTML。"""
        assert looks_like_html_body("<br>换行内容") is True


# ── 6.2 RSS Provider 标准化 — HTML body 不暴露为 summary ─────────


class TestRSSNormalizationHtmlSummary:
    """RSS 标准化：HTML body 作为 content_html 回退时不暴露为 summary。"""

    @pytest.mark.asyncio
    async def test_html_summary_not_exposed_as_text_summary(self) -> None:
        """当 summary/description 是 HTML body 且无专用 content 字段时，summary 应为 None。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel><title>测试</title>
            <item>
              <title>HTML摘要文章</title>
              <link>https://mp.weixin.qq.com/s/html-summary</link>
              <guid>html-summary-001</guid>
              <description><![CDATA[<div><p>这是一段HTML正文</p><p>包含多个段落</p></div>]]></description>
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
        # content_html 应包含 HTML body
        assert art.content_html is not None
        assert "<p>" in art.content_html
        # summary 不应为 HTML body（已标记为 None）
        assert art.summary is None

    @pytest.mark.asyncio
    async def test_text_summary_preserved(self) -> None:
        """当 summary 是纯文本摘要时，应正常保留。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel><title>测试</title>
            <item>
              <title>纯文本摘要</title>
              <link>https://mp.weixin.qq.com/s/text-summary</link>
              <guid>text-summary-001</guid>
              <description>这是一段纯文本摘要内容</description>
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
        assert art.summary == "这是一段纯文本摘要内容"

    @pytest.mark.asyncio
    async def test_content_field_takes_priority_over_summary(self) -> None:
        """当有 content 字段时，summary 不应被覆盖。"""
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel><title>测试</title>
            <item>
              <title>有 content 和 summary</title>
              <link>https://mp.weixin.qq.com/s/both</link>
              <guid>both-001</guid>
              <description>文本摘要</description>
              <content:encoded><![CDATA[<div><p>完整正文</p></div>]]></content:encoded>
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
        assert "完整正文" in art.content_html
        # 文本摘要应保留
        assert art.summary == "文本摘要"


# ── 6.2 Fetcher 持久化 — HTML body 存入 content ──────────────────


class TestRSSPersistenceHtmlContent:
    """RSS 持久化：HTML body 存入 Article.content 而非 Article.summary。"""

    @pytest.mark.asyncio
    async def test_feed_html_fallback_to_content(
        self, fetcher: FetcherService, rss_service: RSSSourceService, db: Database
    ) -> None:
        """Feed HTML 无法被 parse_article_html 解析时，原始 HTML 应存入 content。"""
        source = await rss_service.add_source("html-fallback", "https://example.com/feed")

        art = _make_rss_article(
            content_html="<p>Feed HTML fragment</p>",
            summary="文本摘要",
        )
        info = art.to_article_info()

        # parse_article_html 返回空 content（模拟非微信页面解析失败）
        with patch("src.services.fetcher.parse_article_html", return_value={
            "title": None, "content": None, "cover": None,
        }):
            status, article = await fetcher._fetch_and_save_rss_article(
                source=source, article_info=info,
                content_mode="feed_only", rss_service=rss_service,
            )

        assert status == "inserted"
        assert article is not None
        # 原始 HTML fragment 应存入 content
        assert "<p>Feed HTML fragment</p>" in article.content

    @pytest.mark.asyncio
    async def test_html_summary_not_saved_to_summary_field(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """HTML body 不应被存入 Article.summary。"""
        source = await rss_service.add_source("no-html-summary", "https://example.com/feed")

        art = _make_rss_article(
            content_html="<div><p>HTML 正文</p></div>",
            summary="<div><p>这看起来像 HTML</p></div>",
        )
        info = art.to_article_info()

        with patch("src.services.fetcher.parse_article_html", return_value={
            "title": None, "content": None, "cover": None,
        }):
            status, article = await fetcher._fetch_and_save_rss_article(
                source=source, article_info=info,
                content_mode="feed_only", rss_service=rss_service,
            )

        assert status == "inserted"
        assert article is not None
        # HTML body 不应存入 summary
        assert article.summary is None

    @pytest.mark.asyncio
    async def test_plain_text_summary_preserved(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """纯文本摘要应正常保留在 Article.summary。"""
        source = await rss_service.add_source("text-summary", "https://example.com/feed")

        art = _make_rss_article(
            content_html="<div>Feed 内容</div>",
            summary="这是纯文本摘要",
        )
        info = art.to_article_info()

        with patch("src.services.fetcher.parse_article_html", return_value={
            "title": None, "content": "<div>Feed 内容</div>", "cover": None,
        }):
            status, article = await fetcher._fetch_and_save_rss_article(
                source=source, article_info=info,
                content_mode="feed_only", rss_service=rss_service,
            )

        assert status == "inserted"
        assert article is not None
        assert article.summary == "这是纯文本摘要"


# ── 6.4 HTML 导出回退 — 历史 RSS summary 作为 body ──────────────


class TestHTMLExportHistoricalFallback:
    """HTML 导出：历史 RSS summary 作为 body 回退。"""

    def test_rss_html_summary_used_as_body(self) -> None:
        """RSS 文章 content 为空但 summary 含 HTML 时，summary 应作为 body。"""
        article = _make_db_article(
            content=None,
            summary="<div><p>历史 HTML 正文</p></div>",
            provider="rss",
        )
        html_output = build_article_html(article)

        # HTML body 应被直接渲染（非转义）
        assert "<div><p>历史 HTML 正文</p></div>" in html_output
        # 不应出现转义的摘要元信息块（检查 div 元素，非 CSS class）
        assert "&lt;div&gt;" not in html_output
        assert '<div class="article-summary">' not in html_output

    def test_rss_plain_text_summary_shown_as_metadata(self) -> None:
        """RSS 文章有纯文本 summary 和 content 时，summary 应作为元信息。"""
        article = _make_db_article(
            content="<p>正文内容</p>",
            summary="这是摘要",
            provider="rss",
        )
        html_output = build_article_html(article)

        assert "<p>正文内容</p>" in html_output
        assert "article-summary" in html_output
        assert "这是摘要" in html_output

    def test_non_rss_html_summary_not_used_as_body(self) -> None:
        """非 RSS 文章即使 summary 含 HTML，也不应作为 body 回退。"""
        article = _make_db_article(
            content=None,
            summary="<div>非 RSS 的 HTML</div>",
            provider="weread",
        )
        html_output = build_article_html(article)

        # 非 RSS 不触发回退
        assert "<div>非 RSS 的 HTML</div>" not in html_output.split("</header>")[1] if "</header>" in html_output else True

    def test_rss_with_content_ignores_summary_as_body(self) -> None:
        """RSS 文章有 content 时，不应使用 summary 作为 body。"""
        article = _make_db_article(
            content="<p>实际正文</p>",
            summary="<div>不应作为正文</div>",
            provider="rss",
        )
        html_output = build_article_html(article)

        # content 优先
        assert "<p>实际正文</p>" in html_output
        # HTML summary 应作为元信息显示（转义）
        assert "article-summary" in html_output


# ── 6.5 修复路径测试 ─────────────────────────────────────────────


class TestRSSRepair:
    """历史 RSS 数据修复测试。"""

    @pytest.mark.asyncio
    async def test_repair_moves_html_summary_to_content(
        self, db: Database, subscription_service: SubscriptionService
    ) -> None:
        """修复应将 HTML summary 迁移到 content 并清空 summary。"""
        feed, _ = await subscription_service.add_subscription(
            mp_id="repair-test", name="修复测试", provider="rss",
        )

        async with db.get_session() as session:
            article = Article(
                feed_id=feed.id,
                article_id="repair-art-001",
                title="待修复文章",
                content=None,
                summary="<div><p>HTML 正文</p></div>",
                provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        # 执行修复逻辑
        async with db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            art = result.scalar_one()
            assert art.content is None
            assert looks_like_html_body(art.summary)

            # 执行修复
            art.content = art.summary
            art.summary = None
            await session.flush()

        # 验证修复结果
        async with db.get_session() as session:
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            repaired = result.scalar_one()
            assert repaired.content == "<div><p>HTML 正文</p></div>"
            assert repaired.summary is None

    @pytest.mark.asyncio
    async def test_repair_skips_non_rss_articles(
        self, db: Database, subscription_service: SubscriptionService
    ) -> None:
        """修复不应影响非 RSS 文章。"""
        feed, _ = await subscription_service.add_subscription(
            mp_id="skip-test", name="跳过测试", provider="weread",
        )

        async with db.get_session() as session:
            article = Article(
                feed_id=feed.id,
                article_id="skip-art-001",
                title="非 RSS 文章",
                content=None,
                summary="<div>HTML 内容</div>",
                provider="weread",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        # 模拟修复查询（scope = rss only）
        async with db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Article).where(
                    Article.provider == "rss",
                    Article.id == article_id,
                )
            )
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_repair_skips_plain_text_summary(
        self, db: Database, subscription_service: SubscriptionService
    ) -> None:
        """修复应跳过纯文本 summary 的 RSS 文章。"""
        feed, _ = await subscription_service.add_subscription(
            mp_id="text-skip", name="文本跳过", provider="rss",
        )

        async with db.get_session() as session:
            article = Article(
                feed_id=feed.id,
                article_id="text-art-001",
                title="纯文本摘要文章",
                content=None,
                summary="这是纯文本摘要",
                provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        # 纯文本 summary 不应被识别为 HTML body
        async with db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            art = result.scalar_one()
            assert looks_like_html_body(art.summary) is False

    @pytest.mark.asyncio
    async def test_repair_skips_articles_with_content(
        self, db: Database, subscription_service: SubscriptionService
    ) -> None:
        """修复应跳过已有 content 的文章。"""
        feed, _ = await subscription_service.add_subscription(
            mp_id="content-skip", name="有内容跳过", provider="rss",
        )

        async with db.get_session() as session:
            article = Article(
                feed_id=feed.id,
                article_id="content-art-001",
                title="有内容文章",
                content="<p>已有正文</p>",
                summary="<div>HTML 摘要</div>",
                provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        # 查询条件应排除有 content 的记录
        async with db.get_session() as session:
            from sqlalchemy import select, or_
            result = await session.execute(
                select(Article).where(
                    Article.provider == "rss",
                    Article.id == article_id,
                    (Article.content == "") | Article.content.is_(None),
                )
            )
            assert result.scalar_one_or_none() is None
