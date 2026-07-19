"""市场数据回填服务 - 按交易日期回填历史市场数据缓存。

仅写入支持历史查询的数据分类（volume, limit_up），
跳过实时快照分类，保护历史数据不被实时数据污染。
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.api.finance import FinanceClient
from src.services.market_data_cache_service import MarketDataCacheService
from src.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategoryOutcome:
    """单个分类的回填结果。"""

    category: str
    status: str  # populated | skipped_unsupported | empty | failed
    record_count: int = 0
    message: str = ""


@dataclass(frozen=True)
class BackfillResult:
    """完整回填结果。"""

    trade_date: date
    outcomes: tuple[CategoryOutcome, ...] = ()
    total_populated: int = 0
    total_skipped: int = 0
    total_empty: int = 0
    total_failed: int = 0

    @property
    def is_complete(self) -> bool:
        """所有分类都有数据。"""
        return self.total_populated > 0 and (self.total_empty + self.total_failed) == 0

    @property
    def is_partial(self) -> bool:
        """部分分类有数据。"""
        return self.total_populated > 0 and (self.total_empty + self.total_failed + self.total_skipped) > 0


class MarketDataBackfillService:
    """市场数据回填服务。

    对指定交易日期，仅从支持历史查询的数据源获取数据并写入缓存。
    不支持历史查询的分类被标记为 skipped_unsupported。
    """

    def __init__(self, db: Database, finance_client: FinanceClient | None = None) -> None:
        self.db = db
        self.finance_client = finance_client or FinanceClient()
        self._cache_service = MarketDataCacheService(db, self.finance_client)

    async def backfill(self, trade_date: date) -> BackfillResult:
        """对指定交易日期执行市场数据回填。

        Args:
            trade_date: 目标交易日期

        Returns:
            BackfillResult 包含各分类结果
        """
        capabilities = FinanceClient.get_category_capabilities()
        outcomes: list[CategoryOutcome] = []

        # 收集 historical-safe 分类
        safe_categories = [
            cat for cat, cap in capabilities.items()
            if cap["historical_safe"]
        ]

        # 对每个 historical-safe 分类执行回填
        category_results: dict[str, dict[str, Any]] = {}

        for category in safe_categories:
            try:
                result = await self._fetch_category(category, trade_date)
                if result is not None:
                    category_results[category] = result
                else:
                    outcomes.append(CategoryOutcome(
                        category=category,
                        status="empty",
                        message=f"{category} 数据源返回空",
                    ))
            except Exception as e:
                logger.error("回填 %s 失败 (%s): %s", category, trade_date, e)
                outcomes.append(CategoryOutcome(
                    category=category,
                    status="failed",
                    message=str(e),
                ))

        # 对 unsupported 分类生成 skipped 结果
        for cat, cap in capabilities.items():
            if not cap["historical_safe"]:
                outcomes.append(CategoryOutcome(
                    category=cat,
                    status="skipped_unsupported",
                    message=cap["description"],
                ))

        # 将成功获取的数据写入缓存
        if category_results:
            populated_outcomes = await self._write_backfill_cache(
                trade_date, category_results, outcomes,
            )
            outcomes = populated_outcomes

        # 统计
        total_populated = sum(1 for o in outcomes if o.status == "populated")
        total_skipped = sum(1 for o in outcomes if o.status == "skipped_unsupported")
        total_empty = sum(1 for o in outcomes if o.status == "empty")
        total_failed = sum(1 for o in outcomes if o.status == "failed")

        return BackfillResult(
            trade_date=trade_date,
            outcomes=tuple(outcomes),
            total_populated=total_populated,
            total_skipped=total_skipped,
            total_empty=total_empty,
            total_failed=total_failed,
        )

    async def _fetch_category(
        self, category: str, trade_date: date,
    ) -> dict[str, Any] | None:
        """获取单个分类的历史数据。

        Returns:
            该分类的数据字典，如果为空则返回 None
        """
        if category == "volume":
            volume, _quality = await self.finance_client._get_volume_with_quality(
                trade_date=trade_date,
            )
            if volume.get("total_volume", 0) > 0:
                return {"volume": volume}
            return None

        if category == "limit_up":
            limit_up, _quality = await self.finance_client._get_limit_up_with_quality(
                trade_date=trade_date,
            )
            if limit_up:
                return {"limit_up": limit_up}
            return None

        return None

    async def _write_backfill_cache(
        self,
        trade_date: date,
        category_results: dict[str, dict[str, Any]],
        existing_outcomes: list[CategoryOutcome],
    ) -> list[CategoryOutcome]:
        """将回填数据写入缓存，并更新结果列表。

        仅写入有数据的分类；empty 和 failed 分类不写入（保护已有缓存）。
        """
        # 构造 save_market_data 所需的数据格式
        data: dict[str, Any] = {
            "volume": {},
            "limit_up": [],
            "breadth_quality": {},
        }

        populated_categories: set[str] = set()

        if "volume" in category_results:
            data["volume"] = category_results["volume"]["volume"]
            data["breadth_quality"]["volume"] = {"status": "ok", "source": "backfill"}
            populated_categories.add("volume")

        if "limit_up" in category_results:
            data["limit_up"] = category_results["limit_up"]["limit_up"]
            populated_categories.add("limit_up")

        # 仅在有数据时写入
        if populated_categories:
            await self._cache_service.save_market_data(trade_date, data)

        # 更新 outcomes
        updated: list[CategoryOutcome] = []

        # 保留 skipped_unsupported 和 failed 的原始结果
        for outcome in existing_outcomes:
            if outcome.status in ("skipped_unsupported", "failed"):
                updated.append(outcome)
            elif outcome.status == "empty":
                # empty 的 historical-safe 分类保持 empty
                updated.append(outcome)

        # 为已写入的分类添加 populated 结果
        for cat in populated_categories:
            record_count = 0
            if cat == "volume" and data.get("volume"):
                record_count = 1  # volume 是单条记录
            elif cat == "limit_up":
                record_count = len(data.get("limit_up", []))
            updated.append(CategoryOutcome(
                category=cat,
                status="populated",
                record_count=record_count,
                message=f"{cat} 已写入 {record_count} 条记录",
            ))

        # 为有数据但不在 category_results 中的分类添加 empty
        for cat in ("volume", "limit_up"):
            if cat not in populated_categories:
                # 检查是否已有结果
                if not any(o.category == cat for o in updated):
                    updated.append(CategoryOutcome(
                        category=cat,
                        status="empty",
                        message=f"{cat} 无数据",
                    ))

        return updated
