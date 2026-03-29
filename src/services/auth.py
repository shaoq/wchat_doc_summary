"""认证服务 - 管理微信读书登录和令牌。"""

import logging
from typing import Any

from sqlalchemy import select, update

from src.api.weread import WeReadClient
from src.models.schema import Auth
from src.storage.database import Database

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务。

    管理微信读书登录流程和令牌存储。
    """

    def __init__(self, weread_client: WeReadClient, db: Database):
        """初始化认证服务。

        Args:
            weread_client: 微信读书 API 客户端
            db: 数据库实例
        """
        self.weread_client = weread_client
        self.db = db

    async def start_login(self) -> tuple[str, str]:
        """开始登录流程。

        Returns:
            元组 (login_id, qrcode_url)
            - login_id: 登录会话 ID，用于后续检查登录状态
            - qrcode_url: 二维码图片 URL

        Raises:
            WeReadAPIError: API 调用失败
        """
        logger.info("开始登录流程")

        response = await self.weread_client.get_login_qrcode()
        login_id = response.get("login_id")
        qrcode_url = response.get("qrcode_url")

        if not login_id or not qrcode_url:
            logger.error(f"登录响应格式错误: {response}")
            raise ValueError("登录响应缺少必要字段")

        logger.info(f"获取二维码成功: login_id={login_id}")
        return login_id, qrcode_url

    async def check_login(self, login_id: str) -> dict[str, Any]:
        """检查登录状态。

        如果登录成功，会自动保存 token 到数据库。

        Args:
            login_id: 登录会话 ID

        Returns:
            登录结果字典，包含：
            - success: 是否登录成功
            - token: 令牌（成功时）
            - user_info: 用户信息（成功时）
            - message: 状态消息
            - status: 当前状态 (waiting/scanned/expired/success/error)
        """
        logger.info(f"检查登录状态: {login_id}")

        try:
            response = await self.weread_client.get_login_result(login_id)
            status = response.get("status", "unknown")

            # 处理各种状态
            if status == "expired":
                return {
                    "success": False,
                    "message": "二维码已过期，请重新登录",
                    "status": "expired",
                }

            if status == "error":
                return {
                    "success": False,
                    "message": response.get("message", "登录失败"),
                    "status": "error",
                }

            if status in ("waiting", "pending", "scanned"):
                return {
                    "success": False,
                    "message": response.get("message", "等待扫码或确认"),
                    "status": status,
                }

            # 检查是否登录成功 - 有 token 字段
            token = response.get("token")
            if token:
                # 保存 token 到数据库
                await self._save_token(token, response.get("user_info", {}))

                # 更新客户端 token
                self.weread_client.set_token(token)

                logger.info("登录成功")
                return {
                    "success": True,
                    "token": token,
                    "user_info": response.get("user_info"),
                    "message": "登录成功",
                    "status": "success",
                }

            # 其他情况
            return {
                "success": False,
                "message": response.get("message", "登录失败"),
                "status": status,
            }

        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "status": "error",
            }

    async def _save_token(self, token: str, user_info: dict[str, Any]) -> None:
        """保存令牌到数据库。

        将其他令牌标记为失效。

        Args:
            token: 认证令牌
            user_info: 用户信息
        """
        async with self.db.get_session() as session:
            # 将其他令牌标记为失效
            await session.execute(
                update(Auth).values(status=0)
            )

            # 创建新令牌记录
            auth = Auth(
                token=token,
                username=user_info.get("username") or user_info.get("name"),
                status=1,
            )
            session.add(auth)
            await session.flush()

        logger.info("令牌已保存到数据库")

    async def get_current_token(self) -> str | None:
        """获取当前有效的令牌。

        Returns:
            有效的令牌字符串，无有效令牌返回 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Auth).where(Auth.status == 1).order_by(Auth.created_at.desc())
            )
            auth = result.scalar_one_or_none()

            if auth:
                # 更新客户端 token
                self.weread_client.set_token(auth.token)
                return auth.token

            return None

    async def logout(self) -> None:
        """登出。

        将当前有效令牌标记为失效。
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(Auth).where(Auth.status == 1).values(status=0)
            )

        # 清除客户端 token
        self.weread_client.token = None

        logger.info("已登出")

    async def is_authenticated(self) -> bool:
        """检查是否已认证。

        Returns:
            是否有有效令牌
        """
        token = await self.get_current_token()
        return token is not None

    async def get_auth_info(self) -> dict[str, Any] | None:
        """获取当前认证信息。

        Returns:
            认证信息字典，未认证返回 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Auth).where(Auth.status == 1).order_by(Auth.created_at.desc())
            )
            auth = result.scalar_one_or_none()

            if auth:
                return {
                    "id": auth.id,
                    "username": auth.username,
                    "created_at": auth.created_at.isoformat() if auth.created_at else None,
                }

            return None
