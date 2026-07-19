"""TickFlow 客户端单例。

档位分流（design D2）:
  - 无 key（free 档，默认）→ TickFlow.free()（free-api 服务器，历史日K）
  - 有 key（付费）       → TickFlow(api_key=key, base_url)（付费端点）

进程内单例；key 变化后调用 reset_client()。
"""
from __future__ import annotations

import logging

from tickflow import TickFlow

logger = logging.getLogger(__name__)

_client: TickFlow | None = None


def get_client() -> TickFlow:
    """返回 TickFlow 客户端单例（free 档走 free-api，付费走付费端点）。"""
    global _client
    if _client is None:
        # 延迟 import 避免循环
        from config.settings import settings

        key = settings.tickflow_api_key
        if key:
            base_url = settings.tickflow_base_url or None
            _client = TickFlow(api_key=key, base_url=base_url)
            logger.info("TickFlow 付费客户端已创建 (base_url=%s)", base_url or "default")
        else:
            _client = TickFlow.free()
            logger.info("TickFlow free 客户端已创建 (free-api.tickflow.org)")
    return _client


def reset_client() -> None:
    """重置客户端单例（key 变化或测试用）。"""
    global _client
    _client = None
