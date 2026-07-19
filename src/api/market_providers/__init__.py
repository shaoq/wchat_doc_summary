"""市场数据 Provider 抽象层。

定义统一的 Provider 契约，解耦数据源实现与 FinanceClient。
对齐 src/api/providers/（文章 Provider）的模式。
"""
from .base import (
    BreadthStatistics,
    IndexQuote,
    LimitUpRow,
    MarketDataCategory,
    MarketDataProvider,
    SectorResult,
    SectorRow,
    SnapshotRow,
    VolumeData,
)
from .factory import build_provider_chain

__all__ = [
    "MarketDataProvider",
    "MarketDataCategory",
    "IndexQuote",
    "VolumeData",
    "BreadthStatistics",
    "SectorRow",
    "SectorResult",
    "LimitUpRow",
    "SnapshotRow",
    "build_provider_chain",
]
