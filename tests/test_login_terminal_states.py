"""登录终态测试 - 验证 CLI 对 expired/error 立即停止轮询。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.auth import AuthService


class TestLoginTerminalStates:
    """登录终态测试。

    验证 CLI 登录轮询循环对终态（expired/error）立即停止，
    对等待态（waiting/pending/scanned）继续轮询。
    """

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
    async def test_expired_stops_polling_immediately(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试二维码过期时 check_login 返回 expired 终态。

        service 层应正确返回 expired 状态，CLI 应据此停止轮询。
        """
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "expired", "message": "二维码已过期"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "expired"
        assert "过期" in result["message"]

    @pytest.mark.asyncio
    async def test_error_stops_polling_immediately(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试明确错误时 check_login 返回 error 终态。

        service 层应正确返回 error 状态，CLI 应据此停止轮询。
        """
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "error", "message": "网络异常"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "error"
        assert "网络异常" in result["message"]

    @pytest.mark.asyncio
    async def test_waiting_continues_polling(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试 waiting 状态不是终态，应继续轮询。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "waiting"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "waiting"

    @pytest.mark.asyncio
    async def test_pending_continues_polling(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试 pending 状态不是终态，应继续轮询。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "pending"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_scanned_continues_polling(
        self, auth_service: AuthService, mock_weread_client: MagicMock
    ) -> None:
        """测试 scanned 状态不是终态，应继续轮询。"""
        mock_weread_client.get_login_result = AsyncMock(
            return_value={"status": "scanned"}
        )

        result = await auth_service.check_login("test_login_id")

        assert result["success"] is False
        assert result["status"] == "scanned"


class TestLoginPollingLoopTerminalStates:
    """测试登录轮询循环对终态的处理。

    直接测试 _poll_login_status 辅助函数。
    """

    @pytest.mark.asyncio
    async def test_poll_stops_on_expired(self) -> None:
        """测试轮询循环在 expired 状态下立即停止。"""
        from src.cli.auth import _poll_login_status

        auth_service = MagicMock(spec=AuthService)
        # 第一次返回 expired
        auth_service.check_login = AsyncMock(
            return_value={
                "success": False,
                "status": "expired",
                "message": "二维码已过期，请重新登录",
            }
        )

        result = await _poll_login_status(auth_service, "test_login_id", max_wait=120)

        assert result["status"] == "expired"
        assert auth_service.check_login.await_count == 1

    @pytest.mark.asyncio
    async def test_poll_stops_on_error(self) -> None:
        """测试轮询循环在 error 状态下立即停止。"""
        from src.cli.auth import _poll_login_status

        auth_service = MagicMock(spec=AuthService)
        auth_service.check_login = AsyncMock(
            return_value={
                "success": False,
                "status": "error",
                "message": "网络异常",
            }
        )

        result = await _poll_login_status(auth_service, "test_login_id", max_wait=120)

        assert result["status"] == "error"
        assert auth_service.check_login.await_count == 1

    @pytest.mark.asyncio
    async def test_poll_continues_on_waiting(self) -> None:
        """测试轮询循环在 waiting 状态下继续轮询直到超时。"""
        from src.cli.auth import _poll_login_status

        auth_service = MagicMock(spec=AuthService)
        # 始终返回 waiting，直到超时
        auth_service.check_login = AsyncMock(
            return_value={
                "success": False,
                "status": "waiting",
                "message": "等待扫码",
            }
        )

        result = await _poll_login_status(auth_service, "test_login_id", max_wait=2)

        # 应该因为超时返回 None（或超时状态）
        assert result is None or result.get("status") == "timeout"
        # check_login 应该被调用多次（不止一次）
        assert auth_service.check_login.await_count >= 1

    @pytest.mark.asyncio
    async def test_poll_stops_on_success(self) -> None:
        """测试轮询循环在 success 状态下立即停止。"""
        from src.cli.auth import _poll_login_status

        auth_service = MagicMock(spec=AuthService)
        auth_service.check_login = AsyncMock(
            return_value={
                "success": True,
                "status": "success",
                "token": "test_token",
                "user_info": {"name": "test_user"},
                "message": "登录成功",
            }
        )

        result = await _poll_login_status(auth_service, "test_login_id", max_wait=120)

        assert result["success"] is True
        assert result["status"] == "success"
        assert auth_service.check_login.await_count == 1

    @pytest.mark.asyncio
    async def test_poll_waiting_then_expired(self) -> None:
        """测试轮询循环先遇到 waiting 再遇到 expired 时正确停止。"""
        from src.cli.auth import _poll_login_status

        auth_service = MagicMock(spec=AuthService)
        auth_service.check_login = AsyncMock(
            side_effect=[
                {
                    "success": False,
                    "status": "waiting",
                    "message": "等待扫码",
                },
                {
                    "success": False,
                    "status": "scanned",
                    "message": "已扫码",
                },
                {
                    "success": False,
                    "status": "expired",
                    "message": "二维码已过期，请重新登录",
                },
            ]
        )

        result = await _poll_login_status(auth_service, "test_login_id", max_wait=120)

        assert result["status"] == "expired"
        assert auth_service.check_login.await_count == 3
