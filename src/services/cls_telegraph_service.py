"""财联社电报服务 - 提供电报数据的存储和查询功能。"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from src.api.cls_roll import CLSRollClient
from src.models.schema import CLSTelegraph
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


class CLSTelegraphService:
    """财联社电报服务类。"""

    def __init__(self, db: Database):
        """初始化服务。

        Args:
            db: 数据库实例
        """
        self.db = db

    async def save_telegraphs(
        self,
        telegraphs: list[dict[str, Any]],
        category: str = "red",
    ) -> tuple[int, int]:
        """批量保存电报数据。

        使用 INSERT OR IGNORE 实现去重：已存在的记录会被静默跳过。

最近 Args:
            telegraphs: 电报数据列表
            category: 分类标识

        Returns:
            (新增数量, 跳过数量)
        """
        if not telegraphs:
            return 0, 0

        inserted = 0
        skipped = 0

        async with self.db.get_session() as session:
  # 先查询已存在的 telegraph_id
            telegraph_ids = [str(item.get("id", "")) for item in telegraphs]
            existing_ids = set()

            if telegraph_ids:
                result = await session.execute(
                    select(CLSTelegraph.telegraph_id).where(
                        CLSTelegraph.telegraph_id.in_(telegraph_ids)
                    )
                )
                existing_ids = {row[0] for row in result.all()}

            # 插入不存在的记录
            for item in telegraphs:
                telegraph_id = str(item.get("id", ""))

                if telegraph_id in existing_ids:
                    skipped += 1
                    continue

                # 确保 ctime 是整数类型
                try:
                    ctime_val = int(item.get("ctime", 0))
                except (ValueError, TypeError):
                    ctime_val = 0

                # 直接保存 level 字母（A/B/C），转大写
                level_raw = item.get("level", "C")
                if level_raw and isinstance(level_raw, str):
                    level_val = level_raw.upper() if level_raw.upper() in ("A", "B", "C") else "C"
                else:
                    level_val = "C"

                telegraph = CLSTelegraph(
                    telegraph_id=telegraph_id,
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    ctime=ctime_val,
                    level=level_val,
                    category=category,
                )
                session.add(telegraph)
                inserted += 1

            await session.commit()

        return inserted, skipped

    async def list_telegraphs(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_level: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CLSTelegraph]:
        """查询电报数据。

        Args:
            start_time: 开始时间戳（包含）
            end_time: 结束时间戳（包含）
            min_level: 最低重要程度（"A"/"B"/"C"，A 最重要）。
                       例如 min_level="B" 会返回 A 和 B 级电报
            category: 分类
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            电报列表
        """
        async with self.db.get_session() as session:
            query = select(CLSTelegraph)

            # 时间范围过滤
            if start_time is not None:
                query = query.where(CLSTelegraph.ctime >= start_time)
            if end_time is not None:
                query = query.where(CLSTelegraph.ctime <= end_time)

            # 重要程度过滤（A < B < C，所以用 <= 筛选更重要的）
            if min_level is not None:
                min_level = min_level.upper()
                if min_level in ("A", "B", "C"):
                    query = query.where(CLSTelegraph.level <= min_level)

            # 分类过滤
            if category:
                query = query.where(CLSTelegraph.category == category)

            # 排序（最新的在前）
            query = query.order_by(CLSTelegraph.ctime.desc())

            # 分页
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def ingest_telegraphs(
        self,
        start_time: int,
        end_time: int,
        client: CLSRollClient | None = None,
    ) -> tuple[int, int]:
        """从远端抓取电报后入库（带去重）。

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            client: 财联社 API 客户端（可选，默认创建新实例）

        Returns:
            (新增数量, 跳过数量)
        """
        result = await self.ingest_telegraphs_with_status(
            start_time=start_time,
            end_time=end_time,
            client=client,
        )
        return int(result.get("inserted", 0)), int(result.get("skipped", 0))

    async def ingest_telegraphs_with_status(
        self,
        start_time: int,
        end_time: int,
        client: CLSRollClient | None = None,
    ) -> dict[str, Any]:
        """从远端抓取电报后入库，并返回结构化状态。"""
        if client is None:
            client = CLSRollClient()

        try:
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: client.fetch_by_time_range(start_time, end_time),
            )
        except Exception as e:
            logger.warning(f"抓取远端电报失败: {e}")
            return _build_ingest_result("error", error=str(e))

        if not items:
            return _build_ingest_result("empty")

        inserted, skipped = await self.save_telegraphs(items, category="red")
        logger.info(f"电报入库完成: 新增 {inserted}, 跳过 {skipped} (共 {len(items)} 条)")
        return _build_ingest_result(
            "ok",
            inserted=inserted,
            skipped=skipped,
            fetched=len(items),
        )
