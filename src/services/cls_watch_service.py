"""财联社看盘数据服务 - 提供看盘数据的存储和查询功能。"""

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import select

from src.api.cls_watch import CLSWatchClient
from src.models.schema import CLSWatchData
from src.storage.database import Database

logger = logging.getLogger(__name__)


def _build_ingest_result(
    status: str,
    *,
    inserted: int = 0,
    skipped: int = 0,
    fetched: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    """构造统一的抓取结果结构。"""
    payload: dict[str, Any] = {
        "status": status,
        "inserted": inserted,
        "skipped": skipped,
        "fetched": fetched,
    }
    if error:
        payload["error"] = error
    return payload


class CLSWatchService:
    """财联社看盘数据服务类。"""

    def __init__(self, db: Database):
        """初始化服务。

        Args:
            db: 数据库实例
        """
        self.db = db

    async def save_watch_data(
        self,
        items: list[dict[str, Any]],
        category: str = "watch",
    ) -> tuple[int, int]:
        """批量保存看盘数据。

        使用 INSERT OR IGNORE 实现去重：已存在的记录会被静默跳过。

        Args:
            items: 看盘数据列表
            category: 分类标识

        Returns:
            (新增数量, 跳过数量)
        """
        if not items:
            return 0, 0

        inserted = 0
        skipped = 0

        async with self.db.get_session() as session:
            # 先查询已存在的 watch_id
            watch_ids = [str(item.get("id", "")) for item in items]
            existing_ids = set()

            if watch_ids:
                result = await session.execute(
                    select(CLSWatchData.watch_id).where(
                        CLSWatchData.watch_id.in_(watch_ids)
                    )
                )
                existing_ids = {row[0] for row in result.all()}

            # 插入不存在的记录
            for item in items:
                watch_id = str(item.get("id", ""))

                if watch_id in existing_ids:
                    skipped += 1
                    continue

                # 确保 ctime 是整数类型
                try:
                    ctime_val = int(item.get("ctime", 0))
                except (ValueError, TypeError):
                    ctime_val = 0

                # 提取股票和板块信息
                stocks = item.get("stocks", [])
                sectors = item.get("sectors", [])

                # 确定数据类型
                data_type = "hot"  # 默认为热点数据
                if stocks or sectors:
                    data_type = "stock_comment"  # 个股点评

                watch_data = CLSWatchData(
                    watch_id=watch_id,
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    ctime=ctime_val,
                    category=category,
                    data_type=data_type,
                    stocks=json.dumps(stocks, ensure_ascii=False) if stocks else None,
                    sectors=json.dumps(sectors, ensure_ascii=False) if sectors else None,
                )
                session.add(watch_data)
                inserted += 1

            await session.commit()

        return inserted, skipped

    async def list_watch_data(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        data_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CLSWatchData]:
        """查询看盘数据。

        Args:
            start_time: 开始时间戳（包含）
            end_time: 结束时间戳（包含）
            data_type: 数据类型过滤
            category: 分类过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            看盘数据列表
        """
        async with self.db.get_session() as session:
            query = select(CLSWatchData)

            # 时间范围过滤
            if start_time is not None:
                query = query.where(CLSWatchData.ctime >= start_time)
            if end_time is not None:
                query = query.where(CLSWatchData.ctime <= end_time)

            # 数据类型过滤
            if data_type:
                query = query.where(CLSWatchData.data_type == data_type)

            # 分类过滤
            if category:
                query = query.where(CLSWatchData.category == category)

            # 排序（最新的在前）
            query = query.order_by(CLSWatchData.ctime.desc())

            # 分页
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_watch_data_for_summary(
        self,
        trade_date: date,
        time_window: tuple[datetime, datetime] | None = None,
    ) -> list[dict[str, Any]]:
        """获取指定交易日的看盘数据（用于 AI 摘要生成）。

        时间窗口：trade_date 09:00 ~ trade_date 15:00

        Args:
            trade_date: 交易日期
            time_window: 精确时间窗口 (start, end)，如未提供则自动计算

        Returns:
            看盘数据列表（字典格式）
        """
        if time_window is not None:
            start_dt, end_dt = time_window
        else:
            start_dt = datetime(trade_date.year, trade_date.month, trade_date.day, 9, 0, 0)
            end_dt = datetime(trade_date.year, trade_date.month, trade_date.day, 15, 0, 0)

        start_time = int(start_dt.timestamp())
        end_time = int(end_dt.timestamp())

        items = await self.list_watch_data(
            start_time=start_time,
            end_time=end_time,
            limit=500,  # 获取足够多的数据用于分析
        )

        # 转换为字典格式
        result = []
        for item in items:
            result.append({
                "id": item.id,
                "watch_id": item.watch_id,
                "title": item.title,
                "content": item.content,
                "ctime": item.ctime,
                "publish_time": datetime.fromtimestamp(item.ctime).strftime("%Y-%m-%d %H:%M") if item.ctime else None,
                "data_type": item.data_type,
                "stocks": json.loads(item.stocks) if item.stocks else [],
                "sectors": json.loads(item.sectors) if item.sectors else [],
            })

        return result

    async def get_unique_stocks(self, trade_date: date) -> list[str]:
        """获取指定交易日涉及的所有股票。

        Args:
            trade_date: 交易日期

        Returns:
            股票名称列表（去重）
        """
        items = await self.get_watch_data_for_summary(trade_date)

        stocks = set()
        for item in items:
            for stock in item.get("stocks", []):
                if stock:
                    stocks.add(stock)

        return sorted(list(stocks))

    async def get_unique_sectors(self, trade_date: date) -> list[str]:
        """获取指定交易日涉及的所有板块。

        Args:
            trade_date: 交易日期

        Returns:
            板块名称列表（去重）
        """
        items = await self.get_watch_data_for_summary(trade_date)

        sectors = set()
        for item in items:
            for sector in item.get("sectors", []):
                if sector:
                    sectors.add(sector)

        return sorted(list(sectors))

    async def ingest_watch_data(
        self,
        start_time: int,
        end_time: int,
        client: CLSWatchClient | None = None,
    ) -> tuple[int, int]:
        """从远端抓取看盘数据后入库（带去重）。

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            client: 财联社 API 客户端（可选，默认创建新实例）

        Returns:
            (新增数量, 跳过数量)
        """
        result = await self.ingest_watch_data_with_status(
            start_time=start_time,
            end_time=end_time,
            client=client,
        )
        return int(result.get("inserted", 0)), int(result.get("skipped", 0))

    async def ingest_watch_data_with_status(
        self,
        start_time: int,
        end_time: int,
        client: CLSWatchClient | None = None,
    ) -> dict[str, Any]:
        """从远端抓取看盘数据后入库，并返回结构化状态。"""
        if client is None:
            client = CLSWatchClient()

        try:
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: client.fetch_by_time_range(start_time, end_time),
            )
        except Exception as e:
            logger.warning(f"抓取远端看盘数据失败: {e}")
            return _build_ingest_result("error", error=str(e))

        if not items:
            return _build_ingest_result("empty")

        inserted, skipped = await self.save_watch_data(items)
        logger.info(f"看盘数据入库完成: 新增 {inserted}, 跳过 {skipped} (共 {len(items)} 条)")
        return _build_ingest_result(
            "ok",
            inserted=inserted,
            skipped=skipped,
            fetched=len(items),
        )
