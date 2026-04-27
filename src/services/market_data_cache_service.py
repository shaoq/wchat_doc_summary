"""市场数据缓存服务 - 提供市场数据的本地缓存存储和查询功能。"""

import logging
from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy import delete, select

from src.api.finance import FinanceClient
from src.models.schema import (
    LimitUpStock,
    MarketIndex,
    MarketSector,
    MarketStatistics,
    MarketVolume,
)
import hashlib

from src.storage.database import Database


def _derive_sector_code(sector_data: dict[str, Any]) -> str:
    """从板块数据中派生稳定的缓存标识。

    优先使用原始 code，字段。
    如果 code 为空或缺失，则使用板块名称的 hash 作为稳定标识。

    这样确保不同板块始终有唯一键， 同时即使来源
    无法提供板块代码，缓存仍然稳定。
    """
    code = sector_data.get("code", "")
    if not code:
        # 使用板块名称的 hash 作为稳定标识
        name = sector_data.get("name", "")
        if name:
            code = f"S_{hashlib.md5(name.encode('utf-8')).hexdigest()[:8]}"
        else:
            code = f"SECTOR_{id(id(sector_data))}"
    return code

logger = logging.getLogger(__name__)

# 市场收盘时间（15:05 作为缓冲）
MARKET_CLOSE_TIME = time(15, 5)


class MarketDataCacheService:
    """市场数据缓存服务类。

    提供市场数据（指数、成交额、涨跌统计、板块、涨停股）的本地缓存功能。
    收盘后（15:00）的数据会自动缓存，避免重复调用外部 API。
    """

    def __init__(self, db: Database, finance_client: FinanceClient | None = None):
        """初始化缓存服务。

        Args:
            db: 数据库实例
            finance_client: 财经数据客户端（可选，默认创建新实例）
        """
        self.db = db
        self.finance_client = finance_client or FinanceClient()

    def should_cache(self, trade_date: date) -> bool:
        """判断是否应该缓存数据。

        缓存条件：
        1. 请求的是历史日期（肯定缓存）
        2. 请求的是今天且已过收盘时间（15:05）

        Args:
            trade_date: 交易日期

        Returns:
            是否应该缓存
        """
        today = date.today()
        now = datetime.now()

        # 历史日期：可以缓存
        if trade_date < today:
            return True

        # 今天：需判断是否收盘
        if trade_date == today:
            return now.time() > MARKET_CLOSE_TIME

        return False

    async def get_cached(self, trade_date: date) -> dict[str, Any] | None:
        """从缓存中查询市场数据。

        Args:
            trade_date: 交易日期

        Returns:
            缓存的市场数据，如果没有缓存则返回 None
        """
        async with self.db.get_session() as session:
            # 查询指数数据
            index_result = await session.execute(
                select(MarketIndex).where(MarketIndex.trade_date == trade_date)
            )
            index_data = index_result.scalar_one_or_none()

            # 查询成交额数据
            volume_result = await session.execute(
                select(MarketVolume).where(MarketVolume.trade_date == trade_date)
            )
            volume_data = volume_result.scalar_one_or_none()

            # 查询涨跌统计数据
            stats_result = await session.execute(
                select(MarketStatistics).where(MarketStatistics.trade_date == trade_date)
            )
            stats_data = stats_result.scalar_one_or_none()

            # 查询板块数据
            sectors_result = await session.execute(
                select(MarketSector)
                .where(MarketSector.trade_date == trade_date)
                .order_by(MarketSector.change_pct.desc())
            )
            sectors_data = sectors_result.scalars().all()

            # 查询涨停股数据
            limit_up_result = await session.execute(
                select(LimitUpStock)
                .where(LimitUpStock.trade_date == trade_date)
                .order_by(LimitUpStock.limit_days.desc())
            )
            limit_up_data = limit_up_result.scalars().all()

        # 如果没有任何缓存数据，返回 None
        if not any([index_data, volume_data, stats_data, sectors_data, limit_up_data]):
            return None

        # 构建返回数据
        result = {
            "indices": self._format_index_data(index_data),
            "volume": self._format_volume_data(volume_data),
            "statistics": self._format_statistics_data(stats_data),
            "sectors": self._format_sectors_data(sectors_data),
            "limit_up": self._format_limit_up_data(limit_up_data),
            "fetch_time": index_data.fetch_time.isoformat() if index_data and index_data.fetch_time else None,
            "cached": True,
        }

        logger.debug(f"从缓存获取市场数据: {trade_date}")
        return result

    def _format_index_data(self, index: MarketIndex | None) -> dict[str, Any]:
        """格式化指数数据。"""
        if not index:
            return {}
        return {
            "sh": {
                "name": index.sh_index_name,
                "close": index.sh_index_price,
                "change": index.sh_index_change,
            },
            "sz": {
                "name": index.sz_index_name,
                "close": index.sz_index_price,
                "change": index.sz_index_change,
            },
            "cy": {
                "name": index.cy_index_name,
                "close": index.cy_index_price,
                "change": index.cy_index_change,
            },
        }

    def _format_volume_data(self, volume: MarketVolume | None) -> dict[str, Any]:
        """格式化成交额数据。

        根据 contract，无数据时返回零值 dict 而非空 dict。
        """
        if not volume:
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}
        return {
            "sh_volume": volume.sh_volume or 0,
            "sz_volume": volume.sz_volume or 0,
            "total_volume": volume.total_volume or 0,
        }

    def _format_statistics_data(self, stats: MarketStatistics | None) -> dict[str, Any]:
        """格式化涨跌统计数据。

        根据 contract，无数据时返回零值 dict 而非空 dict。
        """
        if not stats:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}
        return {
            "up_count": stats.up_count or 0,
            "down_count": stats.down_count or 0,
            "flat_count": stats.flat_count or 0,
        }

    def _format_sectors_data(self, sectors: list[MarketSector]) -> dict[str, list]:
        """格式化板块数据。"""
        if not sectors:
            return {"top_sectors": [], "bottom_sectors": []}

        # 按涨跌幅排序
        sorted_sectors = sorted(sectors, key=lambda x: x.change_pct or 0, reverse=True)

        top_sectors = [
            {
                "name": s.sector_name,
                "code": s.sector_code,
                "change": (s.change_pct or 0) / 100,
            }
            for s in sorted_sectors[:10]
        ]

        bottom_sectors = [
            {
                "name": s.sector_name,
                "code": s.sector_code,
                "change": (s.change_pct or 0) / 100,
            }
            for s in sorted_sectors[-10:]
        ]

        return {"top_sectors": top_sectors, "bottom_sectors": bottom_sectors}

    def _format_limit_up_data(self, stocks: list[LimitUpStock]) -> list[dict[str, Any]]:
        """格式化涨停股数据。"""
        return [
            {
                "name": s.stock_name,
                "code": s.stock_code,
                "change": (s.change_pct or 0) / 100,
                "limit_days": s.limit_days or 1,
                "industry": s.industry,
            }
            for s in stocks
        ]

    async def save_market_data(self, trade_date: date, data: dict[str, Any]) -> None:
        """保存市场数据到缓存。

        对每类缓存记录按业务唯一键执行 upsert：
        - MarketIndex / MarketVolume / MarketStatistics 按 trade_date
        - MarketSector 按 (trade_date, sector_code)
        - LimitUpStock 按 (trade_date, stock_code)

        宽度数据（成交额、涨跌统计）仅在 breadth_quality 标记为 ok 时写库，
        避免降级零值污染缓存。

        Args:
            trade_date: 交易日期
            data: 市场数据（来自 FinanceClient.get_all_market_data()）
        """
        async with self.db.get_session() as session:
            fetch_time = datetime.now()
            breadth_quality = data.get("breadth_quality", {})

            # 保存指数数据 — upsert by trade_date
            indices = data.get("indices", {})
            if indices:
                result = await session.execute(
                    select(MarketIndex).where(MarketIndex.trade_date == trade_date)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.sh_index_name = indices.get("sh", {}).get("name")
                    existing.sh_index_price = indices.get("sh", {}).get("close")
                    existing.sh_index_change = indices.get("sh", {}).get("change")
                    existing.sz_index_name = indices.get("sz", {}).get("name")
                    existing.sz_index_price = indices.get("sz", {}).get("close")
                    existing.sz_index_change = indices.get("sz", {}).get("change")
                    existing.cy_index_name = indices.get("cy", {}).get("name")
                    existing.cy_index_price = indices.get("cy", {}).get("close")
                    existing.cy_index_change = indices.get("cy", {}).get("change")
                    existing.fetch_time = fetch_time
                else:
                    session.add(MarketIndex(
                        trade_date=trade_date,
                        sh_index_name=indices.get("sh", {}).get("name"),
                        sh_index_price=indices.get("sh", {}).get("close"),
                        sh_index_change=indices.get("sh", {}).get("change"),
                        sz_index_name=indices.get("sz", {}).get("name"),
                        sz_index_price=indices.get("sz", {}).get("close"),
                        sz_index_change=indices.get("sz", {}).get("change"),
                        cy_index_name=indices.get("cy", {}).get("name"),
                        cy_index_price=indices.get("cy", {}).get("close"),
                        cy_index_change=indices.get("cy", {}).get("change"),
                        fetch_time=fetch_time,
                    ))

            # 保存成交额数据 — 仅在宽度质量 ok 时写库（缺省视为 ok，向后兼容）
            volume_quality = breadth_quality.get("volume", {})
            volume_quality_status = volume_quality.get("status", "ok")
            volume = data.get("volume", {})
            if volume and volume_quality_status == "ok":
                result = await session.execute(
                    select(MarketVolume).where(MarketVolume.trade_date == trade_date)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.sh_volume = volume.get("sh_volume")
                    existing.sz_volume = volume.get("sz_volume")
                    existing.total_volume = volume.get("total_volume")
                    existing.fetch_time = fetch_time
                else:
                    session.add(MarketVolume(
                        trade_date=trade_date,
                        sh_volume=volume.get("sh_volume"),
                        sz_volume=volume.get("sz_volume"),
                        total_volume=volume.get("total_volume"),
                        fetch_time=fetch_time,
                    ))
            elif volume and volume_quality_status != "ok":
                logger.info(
                    "跳过成交额缓存写入: quality=%s", volume_quality_status
                )

            # 保存涨跌统计数据 — ok / near-complete 可写库，partial / error 跳过
            stats_quality = breadth_quality.get("statistics", {})
            stats_quality_status = stats_quality.get("status", "ok")
            statistics = data.get("statistics", {})
            if statistics and stats_quality_status in ("ok", "near-complete"):
                result = await session.execute(
                    select(MarketStatistics).where(MarketStatistics.trade_date == trade_date)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.up_count = statistics.get("up_count")
                    existing.down_count = statistics.get("down_count")
                    existing.flat_count = statistics.get("flat_count")
                    existing.fetch_time = fetch_time
                else:
                    session.add(MarketStatistics(
                        trade_date=trade_date,
                        up_count=statistics.get("up_count"),
                        down_count=statistics.get("down_count"),
                        flat_count=statistics.get("flat_count"),
                        fetch_time=fetch_time,
                    ))
            elif statistics and stats_quality_status not in ("ok", "near-complete"):
                logger.info(
                    "跳过涨跌统计缓存写入: quality=%s", stats_quality_status
                )

            # 保存板块数据 — upsert by (trade_date, sector_code)
            sectors = data.get("sectors", {})
            top_sectors = sectors.get("top_sectors", [])
            bottom_sectors = sectors.get("bottom_sectors", [])
            all_sectors = top_sectors + bottom_sectors

            for sector_data in all_sectors:
                sector_code = sector_data.get("code") or _derive_sector_code(sector_data)
                result = await session.execute(
                    select(MarketSector).where(
                        MarketSector.trade_date == trade_date,
                        MarketSector.sector_code == sector_code,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.sector_name = sector_data.get("name", "")
                    existing.change_pct = (sector_data.get("change", 0) or 0) * 100
                else:
                    session.add(MarketSector(
                        trade_date=trade_date,
                        sector_code=sector_code,
                        sector_name=sector_data.get("name", ""),
                        change_pct=(sector_data.get("change", 0) or 0) * 100,
                    ))

            # 保存涨停股数据 — upsert by (trade_date, stock_code)
            limit_up = data.get("limit_up", [])
            for stock_data in limit_up:
                stock_code = stock_data.get("code", "")
                result = await session.execute(
                    select(LimitUpStock).where(
                        LimitUpStock.trade_date == trade_date,
                        LimitUpStock.stock_code == stock_code,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    existing.stock_name = stock_data.get("name", "")
                    existing.change_pct = (stock_data.get("change", 0) or 0) * 100
                    existing.limit_days = stock_data.get("limit_days", 1)
                    existing.industry = stock_data.get("industry")
                else:
                    session.add(LimitUpStock(
                        trade_date=trade_date,
                        stock_code=stock_code,
                        stock_name=stock_data.get("name", ""),
                        change_pct=(stock_data.get("change", 0) or 0) * 100,
                        limit_days=stock_data.get("limit_days", 1),
                        industry=stock_data.get("industry"),
                    ))

            await session.commit()

        logger.info(f"市场数据已缓存: {trade_date}")

    async def delete_cache(self, trade_date: date) -> int:
        """删除指定日期的缓存数据。

        Args:
            trade_date: 交易日期

        Returns:
            删除的记录数
        """
        total_deleted = 0

        async with self.db.get_session() as session:
            # 删除指数数据
            result = await session.execute(
                delete(MarketIndex).where(MarketIndex.trade_date == trade_date)
            )
            total_deleted += result.rowcount

            # 删除成交额数据
            result = await session.execute(
                delete(MarketVolume).where(MarketVolume.trade_date == trade_date)
            )
            total_deleted += result.rowcount

            # 删除涨跌统计数据
            result = await session.execute(
                delete(MarketStatistics).where(MarketStatistics.trade_date == trade_date)
            )
            total_deleted += result.rowcount

            # 删除板块数据
            result = await session.execute(
                delete(MarketSector).where(MarketSector.trade_date == trade_date)
            )
            total_deleted += result.rowcount

            # 删除涨停股数据
            result = await session.execute(
                delete(LimitUpStock).where(LimitUpStock.trade_date == trade_date)
            )
            total_deleted += result.rowcount

            await session.commit()

        logger.info(f"已删除缓存数据: {trade_date}, 共 {total_deleted} 条记录")
        return total_deleted
