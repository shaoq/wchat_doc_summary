"""服务层测试 - 测试订阅、抓取、认证和 AI 处理服务。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from src.services.subscription import SubscriptionService
from src.services.fetcher import FetcherService, _normalize_publish_time_for_storage
from src.services.auth import AuthService
from src.services.ai_processor import AIProcessor
from src.api.weread import WeReadAPIError
from src.models.schema import Feed, Article, Auth, ArticleProcessing


class TestSubscriptionService:
    """订阅服务测试。"""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """创建模拟数据库实例。"""
        db = MagicMock()
        db.get_session = MagicMock()
        return db

    @pytest.fixture
    def subscription_service(self, mock_db: MagicMock) -> SubscriptionService:
        """创建订阅服务实例。"""
        return SubscriptionService(mock_db)

    @pytest.mark.asyncio
    async def test_add_subscription_new(
        self, subscription_service: SubscriptionService, mock_db: MagicMock
    ) -> None:
        """测试添加新订阅。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        feed = await subscription_service.add_subscription(
            mp_id="MP_WXS_test",
            name="测试公众号",
            intro="测试简介",
        )

        assert feed.mp_id == "MP_WXS_test"
        assert feed.name == "测试公众号"

    @pytest.mark.asyncio
    async def test_add_subscription_existing(
        self, subscription_service: SubscriptionService, mock_db: MagicMock
    ) -> None:
        """测试添加已存在的订阅。"""
        existing_feed = Feed(
            id=1,
            mp_id="MP_WXS_test",
            name="旧名称",
            status=0,
        )

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_feed))
        )
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        feed = await subscription_service.add_subscription(
            mp_id="MP_WXS_test",
            name="新名称",
        )

        assert feed.name == "新名称"
        assert feed.status == 1

    @pytest.mark.asyncio
    async def test_add_subscription_invalid(
        self, subscription_service: SubscriptionService
    ) -> None:
        """测试添加无效订阅。"""
        with pytest.raises(ValueError, match="mp_id 和 name 不能为空"):
            await subscription_service.add_subscription(mp_id="", name="")

    @pytest.mark.asyncio
    async def test_remove_subscription(
        self, subscription_service: SubscriptionService, mock_db: MagicMock
    ) -> None:
        """测试取消订阅。"""
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        success = await subscription_service.remove_subscription("MP_WXS_test")

        assert success is True

    @pytest.mark.asyncio
    async def test_list_subscriptions(
        self, subscription_service: SubscriptionService, mock_db: MagicMock
    ) -> None:
        """测试获取订阅列表。"""
        feeds = [
            Feed(id=1, mp_id="MP_1", name="订阅1", status=1),
            Feed(id=2, mp_id="MP_2", name="订阅2", status=1),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = feeds

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await subscription_service.list_subscriptions()

        assert len(result) == 2


class TestFetcherService:
    """抓取服务测试。"""

    @pytest.fixture
    def mock_weread_client(self) -> MagicMock:
        """创建模拟微信读书客户端。"""
        return MagicMock()

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """创建模拟数据库实例。"""
        return MagicMock()

    @pytest.fixture
    def mock_subscription_service(self) -> MagicMock:
        """创建模拟订阅服务。"""
        return MagicMock()

    @pytest.fixture
    def fetcher_service(
        self,
        mock_weread_client: MagicMock,
        mock_db: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> FetcherService:
        """创建抓取服务实例。"""
        return FetcherService(
            mock_weread_client, mock_db, mock_subscription_service
        )

    @pytest.mark.asyncio
    async def test_get_mp_info_from_article(
        self, fetcher_service: FetcherService, mock_weread_client: MagicMock
    ) -> None:
        """测试从文章链接获取公众号信息。"""
        mock_weread_client.get_mp_info = AsyncMock(
            return_value={
                "mp_id": "MP_WXS_test",
                "name": "测试公众号",
            }
        )

        result = await fetcher_service.get_mp_info_from_article(
            "https://mp.weixin.qq.com/s/test"
        )

        assert result["mp_id"] == "MP_WXS_test"
        assert result["name"] == "测试公众号"

    @pytest.mark.asyncio
    async def test_get_mp_info_from_article_error(
        self, fetcher_service: FetcherService, mock_weread_client: MagicMock
    ) -> None:
        """测试从文章链接获取公众号信息失败。"""
        mock_weread_client.get_mp_info = AsyncMock(
            side_effect=WeReadAPIError("API 错误")
        )

        with pytest.raises(WeReadAPIError):
            await fetcher_service.get_mp_info_from_article(
                "https://mp.weixin.qq.com/s/test"
            )

    @pytest.mark.asyncio
    async def test_fetch_feed_filters_old_articles(
        self,
        fetcher_service: FetcherService,
        mock_weread_client: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """测试按天数抓取时会跳过过旧文章。"""
        now = datetime.now(timezone.utc)
        recent_time = (now - timedelta(hours=1)).isoformat()
        old_time = (now - timedelta(days=10)).isoformat()

        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_WXS_test", name="测试公众号", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()
        mock_weread_client.get_articles = AsyncMock(
            return_value={
                "articles": [
                    {"id": "article_new", "title": "新文章", "publish_time": recent_time},
                    {"id": "article_old", "title": "旧文章", "publish_time": old_time},
                ],
                "page_size": 50,
            }
        )

        saved_article = Article(id=1, feed_id=1, article_id="article_new", title="新文章")
        fetcher_service._fetch_and_save_article = AsyncMock(return_value=saved_article)
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        articles = await fetcher_service.fetch_feed("MP_WXS_test", days=5, max_pages=1)

        assert len(articles) == 1
        assert fetcher_service._fetch_and_save_article.await_count == 1
        saved_payload = fetcher_service._fetch_and_save_article.await_args.args[1]
        assert saved_payload["id"] == "article_new"
        assert saved_payload["title"] == "新文章"
        assert saved_payload["publish_time"] == recent_time
        assert saved_payload["provider"] == "weread"

    def test_normalize_publish_time_for_storage_converts_unix_timestamp_to_shanghai_local(self) -> None:
        """测试 Unix 时间戳会在入库前转成上海本地时间。"""
        normalized = _normalize_publish_time_for_storage(1775046248)

        assert normalized == datetime(2026, 4, 1, 20, 24, 8)

    def test_normalize_publish_time_for_storage_keeps_naive_datetime_unchanged(self) -> None:
        """测试页面解析出的本地 naive 时间不会被二次转换。"""
        parsed_local = datetime(2026, 4, 1, 20, 24, 8)

        normalized = _normalize_publish_time_for_storage(parsed_local)

        assert normalized == parsed_local

    @pytest.mark.asyncio
    async def test_fetch_incremental_stops_at_existing_publish_time(
        self,
        fetcher_service: FetcherService,
        mock_weread_client: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """测试增量抓取遇到旧文章时停止。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_WXS_test", name="测试公众号", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()
        fetcher_service._get_latest_publish_time = AsyncMock(
            return_value=datetime(2026, 1, 2, 9, 0, 0)
        )

        mock_weread_client.get_articles = AsyncMock(
            return_value={
                "articles": [
                    {"id": "article_new", "title": "新文章", "publish_time": "2026-01-03T09:00:00+08:00"},
                    {"id": "article_old", "title": "旧文章", "publish_time": "2026-01-02T09:00:00+08:00"},
                ],
                "page_size": 2,
            }
        )

        saved_article = Article(id=1, feed_id=1, article_id="article_new", title="新文章")
        fetcher_service._fetch_and_save_article = AsyncMock(return_value=saved_article)
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        articles = await fetcher_service.fetch_incremental("MP_WXS_test", max_pages=3, page_size=2)

        assert len(articles) == 1
        assert mock_weread_client.get_articles.await_count == 1
        fetcher_service._fetch_and_save_article.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_feed_latest_count_limits_articles(
        self,
        fetcher_service: FetcherService,
        mock_weread_client: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """测试默认最新文章模式只抓取最新 10 条。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_WXS_test", name="测试公众号", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()
        mock_weread_client.get_articles = AsyncMock(
            return_value={
                "articles": [
                    {"id": f"article_{idx}", "title": f"文章{idx}"}
                    for idx in range(12)
                ],
                "page_size": 10,
            }
        )

        async def save_article(feed_id: int, article_info: dict) -> Article:
            return Article(
                id=1,
                feed_id=feed_id,
                article_id=article_info["id"],
                title=article_info["title"],
            )

        fetcher_service._fetch_and_save_article = AsyncMock(side_effect=save_article)
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        articles = await fetcher_service.fetch_feed("MP_WXS_test", latest_count=10)

        assert len(articles) == 10
        mock_weread_client.get_articles.assert_awaited_once_with(
            "MP_WXS_test",
            page=1,
            page_size=10,
            max_retries_override=0,
            log_http_errors=False,
        )
        fetcher_service.backfill_publish_time.assert_awaited_once_with(
            "MP_WXS_test",
            page_size=10,
            max_pages=1,
        )

    @pytest.mark.asyncio
    async def test_fetch_feed_latest_count_retries_with_smaller_window(
        self,
        fetcher_service: FetcherService,
        mock_weread_client: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """测试默认最新文章模式遇错后会缩小窗口重试。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_WXS_test", name="测试公众号", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()

        call_sizes: list[int] = []

        async def get_articles(
            mp_id: str,
            page: int = 1,
            page_size: int = 50,
            **_: dict,
        ) -> dict:
            call_sizes.append(page_size)
            if page_size == 10:
                raise WeReadAPIError(
                    "API 请求失败: 500",
                    status_code=500,
                    response_text='{"message":"id(931511154): WeReadError400"}',
                )
            return {
                "articles": [
                    {"id": f"article_{idx}", "title": f"文章{idx}"}
                    for idx in range(page_size)
                ],
                "page_size": page_size,
            }

        mock_weread_client.get_articles = AsyncMock(side_effect=get_articles)

        async def save_article(feed_id: int, article_info: dict) -> Article:
            return Article(
                id=1,
                feed_id=feed_id,
                article_id=article_info["id"],
                title=article_info["title"],
            )

        fetcher_service._fetch_and_save_article = AsyncMock(side_effect=save_article)
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        articles = await fetcher_service.fetch_feed("MP_WXS_test", latest_count=10)

        assert len(articles) == 5
        assert call_sizes[:2] == [10, 5]

    @pytest.mark.asyncio
    async def test_fetch_feed_latest_count_reports_aggregated_failure(
        self,
        fetcher_service: FetcherService,
        mock_weread_client: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """测试默认最新文章模式在全部缩窗失败时返回汇总错误。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_WXS_test", name="测试公众号", status=1)
        )
        mock_weread_client.get_articles = AsyncMock(
            side_effect=WeReadAPIError(
                "API 请求失败: 500",
                status_code=500,
                response_text='{"message":"id(931511154): WeReadError400"}',
            )
        )

        with pytest.raises(WeReadAPIError) as exc_info:
            await fetcher_service.fetch_feed("MP_WXS_test", latest_count=10)

        assert "已尝试 pageSize=10/5/3/2/1" in str(exc_info.value)
        assert "id(931511154): WeReadError400" in str(exc_info.value)


class TestAuthService:
    """认证服务测试。"""

    @pytest.fixture
    def mock_weread_client(self) -> MagicMock:
        """创建模拟微信读书客户端。"""
        return MagicMock()

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """创建模拟数据库实例。"""
        return MagicMock()

    @pytest.fixture
    def auth_service(
        self, mock_weread_client: MagicMock, mock_db: MagicMock
    ) -> AuthService:
        """创建认证服务实例。"""
        return AuthService(mock_weread_client, mock_db)

    @pytest.mark.asyncio
    async def test_start_login(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试开始登录。"""
        mock_weread_client.get_login_qrcode = AsyncMock(
            return_value={
                "login_id": "test_id",
                "qrcode_url": "https://example.com/qr.png",
            }
        )

        login_id, qrcode_url = await auth_service.start_login()

        assert login_id == "test_id"
        assert qrcode_url == "https://example.com/qr.png"

    @pytest.mark.asyncio
    async def test_start_login_invalid_response(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试登录响应无效。"""
        mock_weread_client.get_login_qrcode = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="登录响应缺少必要字段"):
            await auth_service.start_login()

    @pytest.mark.asyncio
    async def test_check_login_success(
        self, auth_service: AuthService, mock_weread_client: MagicMock, mock_db: MagicMock
    ) -> None:
        """测试检查登录成功。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={
                "status": "success",
                "message": "登录成功",
                "token": "test_token",
                "user_info": {"name": "test_user"},
            }
        )

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is True
        assert result["token"] == "test_token"

    @pytest.mark.asyncio
    async def test_check_login_expired(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试检查登录二维码过期。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "expired", "message": "二维码已过期", "token": None, "user_info": None}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "expired"

    @pytest.mark.asyncio
    async def test_check_login_error(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试检查登录失败。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "error", "message": "网络异常", "token": None, "user_info": None}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_check_login_waiting(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试检查登录等待中。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "waiting"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "waiting"

    @pytest.mark.asyncio
    async def test_is_authenticated(
        self, auth_service: AuthService, mock_db: MagicMock
    ) -> None:
        """测试检查认证状态。"""
        mock_auth = Auth(id=1, token="test_token", status=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_auth

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        is_auth = await auth_service.is_authenticated()

        assert is_auth is True


class TestAIProcessor:
    """AI 处理器测试。"""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """创建模拟数据库实例。"""
        return MagicMock()

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """创建模拟配置实例。"""
        settings = MagicMock()
        settings.llm_api_key = "test_api_key"
        settings.llm_base_url = "https://api.anthropic.com"
        settings.llm_model = "claude-3-5-haiku-latest"
        settings.max_retries = 3
        return settings

    @pytest.mark.asyncio
    async def test_summarize_article_not_found(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试摘要文章不存在。"""
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_crud = MagicMock()
                mock_crud.get = AsyncMock(return_value=None)
                processor._article_crud = mock_crud

                mock_session = AsyncMock()
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                with pytest.raises(ValueError, match="文章 ID 999 不存在"):
                    await processor.summarize(999)

    @pytest.mark.asyncio
    async def test_extract_keywords(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试提取关键词。"""
        article = Article(
            id=1,
            feed_id=1,
            article_id="test_article",
            title="测试文章",
            content="这是测试内容",
        )

        with patch("src.services.ai_processor.AsyncAnthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "关键词1, 关键词2, 关键词3"
            mock_response.content = [mock_content]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_crud = MagicMock()
                mock_crud.get = AsyncMock(return_value=article)
                mock_crud.update = AsyncMock()
                processor._article_crud = mock_crud

                mock_session = AsyncMock()
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                keywords = await processor.extract_keywords(1)

                assert len(keywords) == 3
                assert "关键词1" in keywords

    def test_build_prompt(self, mock_db: MagicMock, mock_settings: MagicMock) -> None:
        """测试构建提示词。"""
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                prompt = processor._build_prompt(
                    "summarize",
                    "文章内容",
                    title="测试标题",
                    max_length=200,
                )

                assert "测试标题" in prompt
                assert "文章内容" in prompt
                assert "200" in prompt

    def test_init_without_api_key(self, mock_db: MagicMock) -> None:
        """测试未配置 API Key 时初始化失败。"""
        mock_settings_no_key = MagicMock()
        mock_settings_no_key.llm_api_key = None

        with patch("src.services.ai_processor.get_settings", return_value=mock_settings_no_key):
            with pytest.raises(ValueError, match="LLM API Key 未配置"):
                AIProcessor(mock_db)

    @pytest.mark.asyncio
    async def test_extract_stocks(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试提取股票信息。"""
        article = Article(
            id=1,
            feed_id=1,
            article_id="test_article",
            title="股市分析文章",
            content="今天贵州茅台（600519）和宁德时代（300750）表现不错",
        )

        with patch("src.services.ai_processor.AsyncAnthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "贵州茅台（600519），宁德时代（300750）"
            mock_response.content = [mock_content]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_crud = MagicMock()
                mock_crud.get = AsyncMock(return_value=article)
                processor._article_crud = mock_crud

                mock_session = AsyncMock()
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                stocks = await processor.extract_stocks(1)

                assert len(stocks) == 2
                assert "贵州茅台（600519）" in stocks
                assert "宁德时代（300750）" in stocks

    @pytest.mark.asyncio
    async def test_extract_stocks_empty_result(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试提取股票信息返回空结果。"""
        article = Article(
            id=1,
            feed_id=1,
            article_id="test_article",
            title="普通文章",
            content="这是一篇没有股票信息的文章",
        )

        with patch("src.services.ai_processor.AsyncAnthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "无"
            mock_response.content = [mock_content]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_crud = MagicMock()
                mock_crud.get = AsyncMock(return_value=article)
                processor._article_crud = mock_crud

                mock_session = AsyncMock()
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                stocks = await processor.extract_stocks(1)

                assert len(stocks) == 0

    @pytest.mark.asyncio
    async def test_get_processed_articles(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试获取已处理文章列表。"""
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = [1, 3]

                mock_session = AsyncMock()
                mock_session.execute = AsyncMock(return_value=mock_result)
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                processed_ids = await processor._get_processed_articles([1, 2, 3], "extract_stocks")

                assert 1 in processed_ids
                assert 3 in processed_ids
                assert 2 not in processed_ids

    @pytest.mark.asyncio
    async def test_record_processing(
        self, mock_db: MagicMock, mock_settings: MagicMock
    ) -> None:
        """测试记录处理结果。"""
        with patch("src.services.ai_processor.AsyncAnthropic"):
            with patch("src.services.ai_processor.get_settings", return_value=mock_settings):
                processor = AIProcessor(mock_db)

                mock_session = AsyncMock()
                mock_session.add = MagicMock()
                mock_session.flush = AsyncMock()
                mock_session.refresh = AsyncMock()
                mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

                await processor._record_processing(
                    article_id=1,
                    task_type="extract_stocks",
                    status="success",
                    result='["贵州茅台（600519）"]',
                )

                mock_session.add.assert_called_once()


class TestArticleProcessing:
    """文章处理记录模型测试。"""

    def test_model_creation(self) -> None:
        """测试模型创建。"""
        processing = ArticleProcessing(
            id=1,
            article_id=100,
            task_type="extract_stocks",
            status="success",
            result='["贵州茅台（600519）"]',
        )

        assert processing.article_id == 100
        assert processing.task_type == "extract_stocks"
        assert processing.status == "success"
        assert "贵州茅台" in processing.result

    def test_model_repr(self) -> None:
        """测试模型字符串表示。"""
        processing = ArticleProcessing(
            id=1,
            article_id=100,
            task_type="extract_stocks",
            status="success",
        )

        repr_str = repr(processing)
        assert "ArticleProcessing" in repr_str
        assert "extract_stocks" in repr_str
