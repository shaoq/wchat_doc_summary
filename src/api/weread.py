"""微信读书 API 客户端 - 处理与微信读书代理服务的交互。"""

import logging
from typing import Any

import httpx

from config.settings import get_settings
from src.api.request_error import format_request_error

logger = logging.getLogger(__name__)


class WeReadAPIError(Exception):
    """微信读书 API 错误。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self) -> str:
        details: list[str] = [self.message]
        if self.status_code is not None and str(self.status_code) not in self.message:
            details.append(f"status={self.status_code}")
        if self.response_text and self.response_text not in self.message:
            details.append(f"response={self.response_text}")
        return " | ".join(details)


class RateLimitError(WeReadAPIError):
    """WeRead 代理限流错误。

    当代理返回 HTTP 500 且包含 WeReadError400 时抛出，
    表示请求被限流，不应继续重试。
    """


class AuthExpiredError(WeReadAPIError):
    """WeRead Token 失效错误。

    当代理返回 HTTP 401 且包含 WeReadError401 时抛出，
    表示 Token 已失效，需要重新登录。
    """


class WeReadClient:
    """微信读书代理 API 客户端。

    使用 httpx 异步客户端与微信读书代理服务交互。
    """

    def __init__(self, base_url: str | None = None, token: str | None = None):
        """初始化客户端。

        Args:
            base_url: API 基础地址，默认从配置读取
            token: 认证令牌（可选，部分接口需要）
        """
        settings = get_settings()
        self.base_url = (base_url or settings.weread_api_base).rstrip("/")
        self.token = token
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    def _get_headers(self) -> dict[str, str]:
        """获取请求头。

        Returns:
            请求头字典
        """
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; WChatDoc/1.0)",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        allowed_status_codes: set[int] | None = None,
        include_status_code: bool = False,
        max_retries_override: int | None = None,
        log_http_errors: bool = True,
        **kwargs: Any,
    ) -> Any:
        """发送 HTTP 请求。

        Args:
            method: HTTP 方法
            endpoint: API 端点
            **kwargs: 传递给 httpx 的其他参数

        Returns:
            JSON 响应数据；当 include_status_code=True 时，返回
            {"status_code": int, "data": Any}

        Raises:
            WeReadAPIError: API 请求失败
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        kwargs.setdefault("headers", headers)
        kwargs.setdefault("timeout", self.timeout)
        allowed_status_codes = allowed_status_codes or set()
        max_retries = self.max_retries if max_retries_override is None else max_retries_override

        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries + 1):
                try:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code in allowed_status_codes:
                        data = response.json()
                        if include_status_code:
                            return {"status_code": response.status_code, "data": data}
                        return data

                    response.raise_for_status()
                    data = response.json()
                    if include_status_code:
                        return {"status_code": response.status_code, "data": data}
                    return data
                except httpx.HTTPStatusError as e:
                    # 限流检测：500 + WeReadError400 → 立即抛出，不重试
                    if (
                        e.response.status_code == 500
                        and "WeReadError400" in e.response.text
                    ):
                        logger.warning(f"限流检测: {e.response.text}")
                        raise RateLimitError(
                            f"请求被限流: {e.response.text}",
                            status_code=e.response.status_code,
                            response_text=e.response.text,
                        ) from e

                    # Token 失效检测：body 含 WeReadError401 → 立即抛出，不重试
                    if "WeReadError401" in e.response.text:
                        logger.warning(f"Token 失效: {e.response.text}")
                        raise AuthExpiredError(
                            f"Token 已失效: {e.response.text}",
                            status_code=e.response.status_code,
                            response_text=e.response.text,
                        ) from e

                    if log_http_errors:
                        log_fn = logger.error if attempt == max_retries else logger.warning
                        log_fn(
                            f"HTTP 错误: {e.response.status_code} - {e.response.text}"
                        )
                    if attempt == max_retries:
                        raise WeReadAPIError(
                            f"API 请求失败: {e.response.status_code}",
                            status_code=e.response.status_code,
                            response_text=e.response.text,
                        ) from e
                except httpx.RequestError as e:
                    logger.warning(f"请求错误 (尝试 {attempt + 1}): {format_request_error(e)}")
                    if attempt == max_retries:
                        raise WeReadAPIError(f"网络请求失败: {format_request_error(e)}") from e

        raise WeReadAPIError("未知错误")

    async def get_login_qrcode(self) -> dict[str, Any]:
        """获取登录二维码。

        GET /api/v2/login/platform

        Returns:
            包含二维码信息的字典，通常包括：
            - login_id: 登录会话 ID
            - qrcode_url: 二维码图片 URL
        """
        logger.info("获取登录二维码")
        response = await self._request("GET", "/api/v2/login/platform")

        if not isinstance(response, dict):
            return {}

        return {
            "login_id": response.get("login_id") or response.get("id") or response.get("uuid"),
            "qrcode_url": response.get("qrcode_url") or response.get("url") or response.get("scanUrl"),
            "message": response.get("message"),
        }

    async def get_login_result(self, login_id: str) -> dict[str, Any]:
        """获取登录结果。

        GET /api/v2/login/platform/{id}

        注意: 此接口在等待扫码时返回 HTTP 500，body 包含状态码：
        - 402: 等待扫码
        - 666: 二维码已过期
        - 成功时返回 token

        Args:
            login_id: 登录会话 ID

        Returns:
            包含登录结果的字典：
            - status: 状态码 (waiting/scanned/expired/success)
            - token: 认证令牌（成功时）
            - user_info: 用户信息（成功时）
        """
        logger.info(f"检查登录状态: {login_id}")
        response = await self._request(
            "GET",
            f"/api/v2/login/platform/{login_id}",
            allowed_status_codes={500},
            include_status_code=True,
        )

        status_code = response.get("status_code", 200)
        data = response.get("data", {})
        if not isinstance(data, dict):
            data = {}

        # 处理 HTTP 500 但包含登录状态的情况
        if status_code == 500:
            error_code = data.get("message", "")
            if "402" in str(error_code):
                return {
                    "status": "waiting",
                    "message": "等待扫码",
                    "token": None,
                    "user_info": None,
                }
            if "666" in str(error_code):
                return {
                    "status": "expired",
                    "message": "二维码已过期",
                    "token": None,
                    "user_info": None,
                }
            return {
                "status": "error",
                "message": str(error_code) or "登录失败",
                "token": None,
                "user_info": None,
            }

        token = data.get("token")
        user_info = data.get("user_info") or data.get("userInfo")
        status = data.get("status")

        if token:
            return {
                "status": "success",
                "message": data.get("message", "登录成功"),
                "token": token,
                "user_info": user_info or {},
            }

        if status in ("waiting", "pending", "scanned", "expired", "error"):
            return {
                "status": status,
                "message": data.get("message", ""),
                "token": None,
                "user_info": user_info,
            }

        return {
            "status": "error",
            "message": data.get("message", "登录失败"),
            "token": None,
            "user_info": user_info,
        }

    async def get_mp_info(self, article_url: str) -> dict[str, Any]:
        """通过文章链接获取公众号信息。

        POST /api/v2/platform/wxs2mp

        Args:
            article_url: 微信公众号文章链接

        Returns:
            包含公众号信息的字典，包括：
            - mp_id: 公众号 ID
            - name: 公众号名称
            - intro: 简介
            - cover: 封面图片
        """
        logger.info(f"获取公众号信息: {article_url}")
        response = await self._request(
            "POST",
            "/api/v2/platform/wxs2mp",
            json={"url": article_url},
        )

        # 处理 API 返回列表的情况
        if isinstance(response, list):
            if len(response) > 0:
                # 取第一个元素作为公众号信息
                result = response[0] if isinstance(response[0], dict) else {}
                # 标准化字段名
                return {
                    "mp_id": result.get("mp_id") or result.get("mpId") or result.get("id"),
                    "name": result.get("name") or result.get("mp_name") or result.get("mpName"),
                    "intro": result.get("intro") or result.get("description") or result.get("desc", ""),
                    "cover": result.get("cover") or result.get("avatar") or result.get("img", ""),
                }
            return {}

        # 处理字典格式的响应
        if isinstance(response, dict):
            return {
                "mp_id": response.get("mp_id") or response.get("mpId") or response.get("id"),
                "name": response.get("name") or response.get("mp_name") or response.get("mpName"),
                "intro": response.get("intro") or response.get("description") or response.get("desc", ""),
                "cover": response.get("cover") or response.get("avatar") or response.get("img", ""),
            }

        return response

    async def get_articles(
        self,
        mp_id: str,
        page: int = 1,
        page_size: int = 50,
        *,
        max_retries_override: int | None = None,
        log_http_errors: bool = True,
    ) -> dict[str, Any]:
        """获取公众号文章列表。

        GET /api/v2/platform/mps/{mpId}/articles

        Args:
            mp_id: 公众号 ID
            page: 页码，从 1 开始
            page_size: 每页文章数量，默认 50

        Returns:
            包含文章列表的字典，包括：
            - articles: 文章列表
            - total: 总数
            - page: 当前页
            - page_size: 每页数量
        """
        logger.info(f"获取公众号文章列表: mp_id={mp_id}, page={page}, page_size={page_size}")
        params = {"page": page, "pageSize": page_size}
        response = await self._request(
            "GET",
            f"/api/v2/platform/mps/{mp_id}/articles",
            params=params,
            max_retries_override=max_retries_override,
            log_http_errors=log_http_errors,
        )

        if isinstance(response, list):
            return {
                "articles": response,
                "total": len(response),
                "page": page,
                "page_size": len(response),
            }

        if not isinstance(response, dict):
            raise WeReadAPIError(
                f"文章列表响应格式异常，期望 dict 或 list，得到: {type(response).__name__}",
                status_code=None,
                response_text=str(response)[:200],
            )

        return {
            "articles": response.get("articles", []),
            "total": response.get("total", 0),
            "page": response.get("page", page),
            "page_size": response.get("page_size") or response.get("pageSize", page_size),
        }

    def set_token(self, token: str) -> None:
        """设置认证令牌。

        Args:
            token: 认证令牌
        """
        self.token = token
        logger.info("已更新认证令牌")
