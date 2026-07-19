"""市场数据 Provider 工厂——按配置组装 per-category Provider 链。

设计为纯函数（接受已实例化的 Provider 字典），将具体 Provider 的实例化
推迟到应用层，便于单测（mock 注入）与延迟导入（TickFlow/Legacy Provider
在各自模块实现后注入）。
"""
from __future__ import annotations

from typing import Literal

from .base import MarketDataCategory, MarketDataProvider

ProviderMode = Literal["mixed", "tickflow"]


def build_provider_chain(
    category: MarketDataCategory,
    providers: dict[str, MarketDataProvider],
    mode: ProviderMode = "mixed",
) -> list[MarketDataProvider]:
    """按 mode 组装某分类的 Provider 链（有序：主源在前，fallback 在后）。

    Args:
        category: 市场数据分类（当前实现下，链组装与分类无关，保留参数供未来按分类定制）。
        providers: 已实例化的 Provider 字典，约定 key:
            "tickflow" → TickFlow free Provider
            "legacy"   → 原 akshare/pytdx/东财 Provider
        mode: "tickflow"（仅 TickFlow）/ "mixed"（TickFlow 主 + legacy fallback）。

    Returns:
        有序 Provider 列表；缺失的 Provider 跳过。
    """
    tf = providers.get("tickflow")
    legacy = providers.get("legacy")

    if mode == "tickflow":
        return [tf] if tf is not None else []

    # mixed: TickFlow 主源 + legacy fallback
    chain: list[MarketDataProvider] = []
    if tf is not None:
        chain.append(tf)
    if legacy is not None:
        chain.append(legacy)
    return chain
