"""API 层测试 - 测试微信读书客户端和文章抓取功能。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.api.weread import WeReadClient, WeReadAPIError
from src.api.article import (
    fetch_article_content,
    parse_article_html,
    extract_images,
    ArticleFetchError,
)


class TestWeReadClient:
    """微信读书客户端测试。"""

    def test_client_init(self) -> None:
        """测试客户端初始化。"""
        client = WeReadClient(base_url="https://api.example.com", token="test_token")

        assert client.base_url == "https://api.example.com"
        assert client.token == "test_token"

    def test_client_init_default(self) -> None:
        """测试客户端使用默认配置初始化。"""
        with patch("src.api.weread.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                weread_api_base="https://default.api.com",
                request_timeout=30,
                max_retries=3,
            )
            client = WeReadClient()

            assert client.base_url == "https://default.api.com"

    def test_get_headers_without_token(self) -> None:
        """测试无 token 时的请求头。"""
        client = WeReadClient(base_url="https://api.example.com")
        headers = client._get_headers()

        assert "Accept" in headers
        assert "User-Agent" in headers
        assert "Authorization" not in headers

    def test_get_headers_with_token(self) -> None:
        """测试有 token 时的请求头。"""
        client = WeReadClient(base_url="https://api.example.com", token="my_token")
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer my_token"

    @pytest.mark.asyncio
    async def test_get_login_qrcode(self) -> None:
        """测试获取登录二维码。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "login_id": "test_login_id",
            "qrcode_url": "https://example.com/qrcode.png",
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_login_qrcode()

            assert result["login_id"] == "test_login_id"
            assert result["qrcode_url"] == "https://example.com/qrcode.png"

    @pytest.mark.asyncio
    async def test_get_login_result(self) -> None:
        """测试获取登录结果。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "status_code": 200,
            "data": {
                "token": "test_token",
                "user_info": {"name": "test_user"},
            },
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_login_result("test_login_id")

            assert result["status"] == "success"
            assert result["token"] == "test_token"
            assert result["user_info"]["name"] == "test_user"

    @pytest.mark.asyncio
    async def test_get_login_result_waiting(self) -> None:
        """测试获取登录结果 - 等待扫码。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "status_code": 500,
            "data": {"message": "402 waiting"},
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_login_result("test_login_id")

            assert result["status"] == "waiting"
            assert result["token"] is None

    @pytest.mark.asyncio
    async def test_get_login_result_expired(self) -> None:
        """测试获取登录结果 - 二维码过期。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "status_code": 500,
            "data": {"message": "666 expired"},
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_login_result("test_login_id")

            assert result["status"] == "expired"
            assert result["token"] is None

    @pytest.mark.asyncio
    async def test_get_mp_info(self) -> None:
        """测试获取公众号信息。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "mp_id": "MP_WXS_test",
            "name": "测试公众号",
            "intro": "这是一个测试公众号",
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_mp_info("https://mp.weixin.qq.com/s/test")

            assert result["mp_id"] == "MP_WXS_test"
            assert result["name"] == "测试公众号"

    @pytest.mark.asyncio
    async def test_get_articles(self) -> None:
        """测试获取文章列表。"""
        client = WeReadClient(base_url="https://api.example.com")

        mock_response = {
            "articles": [
                {"id": "article_1", "title": "文章1"},
                {"id": "article_2", "title": "文章2"},
            ],
            "total": 2,
            "page": 1,
        }

        with patch.object(
            client, "_request", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.get_articles("MP_WXS_test", page=1)

            assert len(result["articles"]) == 2
            assert result["total"] == 2
            assert result["page_size"] == 50

    @pytest.mark.asyncio
    async def test_request_http_error_preserves_context(self) -> None:
        """测试 HTTP 错误会保留状态码和响应上下文。"""
        client = WeReadClient(base_url="https://api.example.com")
        client.max_retries = 0

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = '{"message":"id(931511154): WeReadError400"}'
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(WeReadAPIError) as exc_info:
                await client._request("GET", "/api/v2/platform/mps/MP_WXS_test/articles")

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_text == '{"message":"id(931511154): WeReadError400"}'
        assert "id(931511154): WeReadError400" in str(exc_info.value)

    def test_set_token(self) -> None:
        """测试设置 token。"""
        client = WeReadClient(base_url="https://api.example.com")
        client.set_token("new_token")

        assert client.token == "new_token"


class TestArticleAPI:
    """文章抓取 API 测试。"""

    @pytest.mark.asyncio
    async def test_fetch_article_content_success(self) -> None:
        """测试成功获取文章内容。"""
        html_content = "<html><body>Test content</body></html>"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = html_content
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_article_content("test_article_id")
            assert result == html_content

    @pytest.mark.asyncio
    async def test_fetch_article_content_with_full_url(self) -> None:
        """测试使用完整文章 URL 获取内容。"""
        html_content = "<html><body>Test content</body></html>"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = html_content
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_article_content("https://mp.weixin.qq.com/s/test_article_id")

            assert result == html_content
            mock_client.return_value.__aenter__.return_value.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_article_content_failure(self) -> None:
        """测试获取文章内容失败。"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Error", request=MagicMock(), response=MagicMock(status_code=404)
                )
            )

            with pytest.raises(ArticleFetchError):
                await fetch_article_content("invalid_id")

    def test_parse_article_html(self) -> None:
        """测试解析文章 HTML。"""
        html = """
        <html>
        <head>
            <meta property="og:title" content="测试标题">
            <meta property="og:image" content="https://example.com/cover.jpg">
        </head>
        <body>
            <h1 class="rich_media_title">测试标题</h1>
            <a id="js_name">测试公众号</a>
            <em id="publish_time">2024-01-01</em>
            <div id="js_content">这是文章正文内容</div>
        </body>
        </html>
        """

        result = parse_article_html(html)

        assert result["title"] == "测试标题"
        assert result["author"] == "测试公众号"
        assert result["cover"] == "https://example.com/cover.jpg"
        assert result["content"] is not None
        assert "文章正文内容" in result["content"]

    def test_parse_article_html_empty(self) -> None:
        """测试解析空 HTML。"""
        html = "<html><body></body></html>"

        result = parse_article_html(html)

        assert result["title"] is None
        assert result["content"] is None
        assert result["author"] is None

    def test_extract_images(self) -> None:
        """测试提取图片。"""
        html = """
        <html>
        <body>
            <img src="https://example.com/img1.jpg">
            <img data-src="https://example.com/img2.jpg">
            <img src="invalid_url">
        </body>
        </html>
        """

        images = extract_images(html)

        assert len(images) == 2
        assert "https://example.com/img1.jpg" in images
        assert "https://example.com/img2.jpg" in images


class TestWeReadAPIError:
    """API 错误测试。"""

    def test_error_creation(self) -> None:
        """测试创建错误。"""
        error = WeReadAPIError("API 请求失败")

        assert str(error) == "API 请求失败"
        assert isinstance(error, Exception)

    def test_error_creation_with_context(self) -> None:
        """测试带上下文的错误字符串。"""
        error = WeReadAPIError(
            "API 请求失败: 500",
            status_code=500,
            response_text='{"message":"id(931511154): WeReadError400"}',
        )

        assert error.status_code == 500
        assert error.response_text is not None
        assert "id(931511154): WeReadError400" in str(error)
