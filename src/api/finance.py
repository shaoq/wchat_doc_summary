"""财经数据 API 客户端 - 使用 akshare 获取 A 股市场数据。"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import akshare as ak

logger = logging.getLogger(__name__)


class FinanceAPIError(Exception):
    """财经 API 错误。"""

    pass


class FinanceClient:
    """财经数据客户端。

    使用 akshare 库获取 A 股市场数据。
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """初始化客户端。

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._semaphore = asyncio.Semaphore(3)

    async def _retry_request(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """带重试的请求封装。

        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            FinanceAPIError: 请求失败
        """
        async with self._semaphore:
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    # akshare 是同步库，在线程池中运行
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                except Exception as e:
                    last_error = e
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))

            raise FinanceAPIError(f"请求失败: {last_error}")

    async def get_index_data(self) -> dict[str, Any]:
        """获取 A 股主要指数数据。

        Returns:
            指数数据字典:
            {
                "sh": {"name": "上证指数", "close": 3000.0, "change": 0.01},
                "sz": {"name": "深证成指", "close": 10000.0, "change": -0.02},
                "cy": {"name": "创业板指", "close": 2000.0, "change": 0.03}
            }
        """
        try:
            # 获取实时行情数据
            df = await self._retry_request(ak.stock_zh_index_spot_em)

            # 提取主要指数
            indices = {}
            index_map = {
                "上证指数": "sh",
                "深证成指": "sz",
                "创业板指": "cy",
            }

            for _, row in df.iterrows():
                name = row.get("名称", "")
                if name in index_map:
                    key = index_map[name]
                    close = float(row.get("最新价", 0))
                    change_pct = float(row.get("涨跌幅", 0))
                    indices[key] = {
                        "name": name,
                        "close": close,
                        "change": change_pct / 100,  # 转换为小数
                    }

            return indices

        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return {}

    async def get_volume_data(self) -> dict[str, float]:
        """获取两市成交额数据。

        Returns:
            成交额数据:
            {
                "sh_volume": 3000.5,  # 沪市成交额（亿元）
                "sz_volume": 4000.2,  # 深市成交额（亿元）
                "total_volume": 7000.7  # 总成交额（亿元）
            }
        """
        try:
            df = await self._retry_request(ak.stock_zh_a_spot_em)

            # 计算成交额（单位：元 -> 亿元）
            sh_volume = 0.0
            sz_volume = 0.0

            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                amount = float(row.get("成交额", 0) or 0)

                if code.startswith("6"):  # 上海
                    sh_volume += amount
                elif code.startswith(("0", "3")):  # 深圳
                    sz_volume += amount

            # 转换为亿元
            sh_volume = round(sh_volume / 1e8, 2)
            sz_volume = round(sz_volume / 1e8, 2)

            return {
                "sh_volume": sh_volume,
                "sz_volume": sz_volume,
                "total_volume": round(sh_volume + sz_volume, 2),
            }

        except Exception as e:
            logger.error(f"获取成交量数据失败: {e}")
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    async def get_statistics(self) -> dict[str, int]:
        """获取涨跌统计数据。

        Returns:
            统计数据:
            {
                "up_count": 2000,    # 上涨家数
                "down_count": 2500,  # 下跌家数
                "flat_count": 500    # 平盘家数
            }
        """
        try:
            df = await self._retry_request(ak.stock_zh_a_spot_em)

            up_count = 0
            down_count = 0
            flat_count = 0

            for _, row in df.iterrows():
                change = float(row.get("涨跌幅", 0) or 0)
                if change > 0:
                    up_count += 1
                elif change < 0:
                    down_count += 1
                else:
                    flat_count += 1

            return {
                "up_count": up_count,
                "down_count": down_count,
                "flat_count": flat_count,
            }

        except Exception as e:
            logger.error(f"获取涨跌统计失败: {e}")
            return {"up_count": 0, "down_count": 0, "flat_count": 0}

    async def get_sector_data(self, top_n: int = 5) -> dict[str, list]:
        """获取板块涨跌数据。

        Args:
            top_n: 返回前 N 个板块

        Returns:
            板块数据:
            {
                "top_sectors": [
                    {"name": "人工智能", "change": 0.05},
                    ...
                ],
                "bottom_sectors": [
                    {"name": "银行", "change": -0.03},
                    ...
                ]
            }
        """
        try:
            df = await self._retry_request(ak.stock_board_concept_name_em)

            # 按涨跌幅排序
            df = df.sort_values(by="涨跌幅", ascending=False)

            top_sectors = []
            for _, row in df.head(top_n).iterrows():
                top_sectors.append({
                    "name": row.get("板块名称", ""),
                    "change": float(row.get("涨跌幅", 0) or 0) / 100,
                })

            bottom_sectors = []
            for _, row in df.tail(top_n).iterrows():
                bottom_sectors.append({
                    "name": row.get("板块名称", ""),
                    "change": float(row.get("涨跌幅", 0) or 0) / 100,
                })

            return {
                "top_sectors": top_sectors,
                "bottom_sectors": bottom_sectors,
            }

        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return {"top_sectors": [], "bottom_sectors": []}

    async def get_limit_up_stocks(self, min_days: int = 2) -> list[dict[str, Any]]:
        """获取连板个股数据。

        Args:
            min_days: 最小连板天数

        Returns:
            连板个股列表:
            [
                {"name": "某某股份", "code": "000001", "days": 3},
                ...
            ]
        """
        try:
            df = await self._retry_request(ak.stock_zh_a_spot_em)

            # 筛选涨停股（涨跌幅 >= 9.9%）
            limit_up = df[df["涨跌幅"] >= 9.9].copy()

            # 计算连板（简化：这里用当日涨停作为筛选条件）
            # 实际连板判断需要历史数据，这里返回涨停股
            stocks = []
            for _, row in limit_up.head(20).iterrows():
                stocks.append({
                    "name": row.get("名称", ""),
                    "code": row.get("代码", ""),
                    "change": float(row.get("涨跌幅", 0) or 0) / 100,
                })

            return stocks

        except Exception as e:
            logger.error(f"获取连板数据失败: {e}")
            return []

    async def get_all_market_data(self) -> dict[str, Any]:
        """获取所有市场数据。

        Returns:
            完整的市场数据字典
        """
        logger.info("开始获取市场数据...")

        # 并发获取所有数据
        results = await asyncio.gather(
            self.get_index_data(),
            self.get_volume_data(),
            self.get_statistics(),
            self.get_sector_data(),
            self.get_limit_up_stocks(),
            return_exceptions=True,
        )

        # 处理结果
        market_data = {
            "indices": results[0] if not isinstance(results[0], Exception) else {},
            "volume": results[1] if not isinstance(results[1], Exception) else {},
            "statistics": results[2] if not isinstance(results[2], Exception) else {},
            "sectors": results[3] if not isinstance(results[3], Exception) else {},
            "limit_up": results[4] if not isinstance(results[4], Exception) else [],
            "fetch_time": datetime.now().isoformat(),
        }

        logger.info("市场数据获取完成")
        return market_data
