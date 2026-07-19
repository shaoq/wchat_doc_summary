"""市场数据 Provider 抽象基类与返回类型 dataclass。

返回类型对齐 FinanceClient.get_all_market_data() 的 dict 契约：
  - indices  → {sh/sz/cy: IndexQuote}        → 扁平化为 sh_index_*/sz_*/cy_*
  - volume   → VolumeData                    → {sh_volume, sz_volume, total_volume}
  - statistics → BreadthStatistics           → {up_count, down_count, flat_count}
  - sectors  → SectorResult                  → {top_sectors, bottom_sectors}
  - limit_up → list[LimitUpRow]              → [{stock_code, stock_name, change_pct, ...}]
  - snapshot → list[SnapshotRow]

涨跌幅统一用内部小数口径（0.0123 = +1.23%），规避 _normalize_pct 双重缩放。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


# ===== 返回类型 dataclass =====


@dataclass(frozen=True)
class IndexQuote:
    """单个指数行情。"""

    name: str
    price: float | None
    change: float | None  # 涨跌幅（小数口径）


@dataclass(frozen=True)
class VolumeData:
    """两市成交额（亿元）。"""

    sh_volume: float | None
    sz_volume: float | None
    total_volume: float | None


@dataclass(frozen=True)
class BreadthStatistics:
    """涨跌家数统计。"""

    up_count: int
    down_count: int
    flat_count: int


@dataclass(frozen=True)
class SectorRow:
    """板块（行业）单行。"""

    sector_code: str
    sector_name: str
    change_pct: float | None  # 小数口径
    amount: float | None = None
    main_inflow: float | None = None


@dataclass(frozen=True)
class SectorResult:
    """板块涨跌排行（top + bottom）。"""

    top_sectors: list[SectorRow] = field(default_factory=list)
    bottom_sectors: list[SectorRow] = field(default_factory=list)


@dataclass(frozen=True)
class LimitUpRow:
    """涨停股单行。"""

    stock_code: str
    stock_name: str
    change_pct: float | None  # 小数口径
    limit_days: int | None = None
    industry: str | None = None


@dataclass(frozen=True)
class SnapshotRow:
    """全市场快照单行。"""

    symbol: str
    name: str | None
    price: float | None
    change_pct: float | None  # 小数口径
    volume: float | None = None
    amount: float | None = None


# 6 分类标识
MarketDataCategory = Literal[
    "indices", "volume", "statistics", "sectors", "limit_up", "snapshot"
]


class MarketDataProvider:
    """市场数据 Provider 基类。

    6 个分类方法，返回 dataclass 或 None。None 表示该 Provider 不支持此分类，
    编排层 fallback 到链中下一个 Provider。

    元数据:
        name: Provider 名称（日志 / 质量标记用）
        supports_historical: 是否支持按历史交易日取数（回填门控）
    """

    name: str = "base"
    supports_historical: bool = False

    async def get_indices(
        self, trade_date: date | None = None
    ) -> dict[str, IndexQuote] | None:
        return None

    async def get_volume(
        self, trade_date: date | None = None
    ) -> VolumeData | None:
        return None

    async def get_statistics(
        self, trade_date: date | None = None
    ) -> BreadthStatistics | None:
        return None

    async def get_sectors(
        self, trade_date: date | None = None, top_n: int = 10
    ) -> SectorResult | None:
        return None

    async def get_limit_up(
        self, trade_date: date | None = None
    ) -> list[LimitUpRow] | None:
        return None

    async def get_snapshot(
        self, trade_date: date | None = None
    ) -> list[SnapshotRow] | None:
        return None
