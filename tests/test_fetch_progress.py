"""FetchProgressEvent 单元测试。"""

from src.services.fetcher import FetchProgressEvent


class TestFetchProgressEvent:
    def test_subscription_start(self) -> None:
        event = FetchProgressEvent.subscription_start("mp1", "测试号", 1, 10)
        assert event.type == "subscription_start"
        assert event.mp_id == "mp1"
        assert event.feed_name == "测试号"
        assert "[1/10]" in event.detail

    def test_page_fetched(self) -> None:
        event = FetchProgressEvent.page_fetched("mp1", page=2, article_count=15)
        assert event.type == "page_fetch"
        assert "2" in event.detail
        assert "15" in event.detail

    def test_article_fetched_new(self) -> None:
        event = FetchProgressEvent.article_fetched("mp1", "文章标题", is_new=True)
        assert event.type == "article_fetch"
        assert "新" in event.detail

    def test_article_fetched_failed(self) -> None:
        event = FetchProgressEvent.article_fetched("mp1", "文章标题", is_new=False)
        assert "失败" in event.detail

    def test_article_skipped(self) -> None:
        event = FetchProgressEvent.article_skipped("mp1", "已有文章")
        assert event.type == "article_skip"
        assert "已存在" in event.detail

    def test_subscription_done(self) -> None:
        event = FetchProgressEvent.subscription_done("mp1", "测试号", inserted=3, existing=5)
        assert event.type == "subscription_done"
        assert "3" in event.detail
        assert "5" in event.detail

    def test_waiting(self) -> None:
        event = FetchProgressEvent.waiting("mp1", 6.2)
        assert event.type == "waiting"
        assert "6.2s" in event.detail

    def test_rate_limited_event(self) -> None:
        event = FetchProgressEvent.rate_limited_event("mp1", wait_seconds=23, limit=12, window=60)
        assert event.type == "rate_limited"
        assert "12" in event.detail
