"""财经数据 API 客户端 - 多数据源获取 A 股市场数据。

支持数据源：
- 腾讯财经 (主要) - 稳定性好
- 东方财富/akshare (备用)
"""

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime
from threading import Lock
from typing import Any, Optional

import akshare as ak
import httpx
import requests

logger = logging.getLogger(__name__)

# 是否禁用网络请求（用于测试或离线模式）
_DISABLE_NETWORK = os.environ.get("WCHAT_DISABLE_NETWORK", "").lower() in ("1", "true", "yes")

# 缓存配置
_CACHE_TTL_SECONDS = 300  # 5 分钟缓存
_cache: dict[str, Any] = {"data": None, "fetched_at": None, "lock": Lock()}


class FinanceAPIError(Exception):
    """财经 API 错误。"""

    pass


class EastMoneyCurlClient:
    """东方财富 curl 客户端 - 使用 curl 绕过 Python HTTP 库问题。

    东方财富服务器对 Python HTTP 库有反爬虫机制，
    使用 curl 可以绕过这个问题。
    """

    # API 端点
    STOCK_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
    BOARD_LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"

    # A股筛选条件: m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23
    # m:0+t:6 - 上海A股  m:0+t:80 - 上海B股  m:1+t:2 - 深圳A股  m:1+t:23 - 深圳B股
    A_STOCK_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"

    # 概念板块筛选条件
    CONCEPT_BOARD_FS = "b:MK0021,b:MK0022,b:MK0023,b:MK0024"

    # 字段映射: f12=代码, f14=名称, f2=最新价, f3=涨跌幅, f6=成交额(元)
    STOCK_FIELDS = "f12,f14,f2,f3,f6"
    BOARD_FIELDS = "f12,f14,f2,f3"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def _fetch_with_curl(self, url: str) -> Optional[dict]:
        """使用 curl 获取数据。

        使用 --noproxy '*' 绕过系统代理，避免代理兼容性问题。
        """
        try:
            result = subprocess.run(
                [
                    "curl", "-s", "--noproxy", "*",
                    "--connect-timeout", str(int(self.timeout)),
                    url
                ],
                capture_output=True,
                text=False,
                timeout=self.timeout + 5,
            )

            # exit code 52 = Empty reply from server
            if result.returncode == 52:
                logger.warning("东方财富服务器返回空响应（可能是非交易时间）")
                return None

            if result.returncode != 0:
                logger.warning(f"curl 失败 (code {result.returncode}): {result.stderr.decode('utf-8', errors='ignore')}")
                return None

            text = result.stdout.decode("utf-8", errors="ignore")
            if not text:
                logger.warning("curl 返回空响应")
                return None

            data = eval(text)  # 东方财富返回的是 JavaScript 对象格式
            return data

        except subprocess.TimeoutExpired:
            logger.warning("curl 请求超时")
            return None
        except FileNotFoundError:
            logger.warning("curl 命令不可用")
            return None
        except Exception as e:
            logger.warning(f"curl 获取失败: {e}")
            return None

    def get_stock_list(self, page: int = 1, page_size: int = 5000) -> Optional[dict]:
        """获取 A 股实时行情列表。"""
        url = (
            f"{self.STOCK_LIST_URL}?"
            f"fs={self.A_STOCK_FS}&"
            f"fields={self.STOCK_FIELDS}&"
            f"pn={page}&"
            f"pz={page_size}&"
            f"ut=fa5fd1943c7b386f1722cd529f11d4db"
        )
        return self._fetch_with_curl(url)

    def get_board_list(self, page: int = 1, page_size: int = 200) -> Optional[dict]:
        """获取概念板块列表。"""
        url = (
            f"{self.BOARD_LIST_URL}?"
            f"fs={self.CONCEPT_BOARD_FS}&"
            f"fields={self.BOARD_FIELDS}&"
            f"pn={page}&"
            f"pz={page_size}&"
            f"ut=fa5fd1943c7b386f1722cd529f11d4db"
        )
        return self._fetch_with_curl(url)


class TencentFinanceClient:
    """腾讯财经数据源 - 稳定的备用数据源。

    使用 curl 命令绕过 Python 库的 TLS 差异问题。
    """

    # 腾讯指数代码格式：s_前缀用于指数
    INDEX_CODES = {
        "s_sh000001": ("上证指数", "sh"),
        "s_sz399001": ("深证成指", "sz"),
        "s_sz399006": ("创业板指", "cy"),
    }

    # API 端点
    API_URL = "https://web.sqt.gtimg.cn/q={codes}"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def get_index_data_sync(self) -> dict[str, Any]:
        """同步获取指数数据。"""
        codes = ",".join(self.INDEX_CODES.keys())  # 使用逗号分隔
        url = self.API_URL.format(codes=codes)

        try:
            # 使用 curl 绕过 Python TLS 问题
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", str(int(self.timeout)), url],
                capture_output=True,
                text=False,  # 返回 bytes
                timeout=self.timeout + 5,
            )

            if result.returncode != 0:
                logger.warning(f"curl 失败: {result.stderr.decode('utf-8', errors='ignore')}")
                return {}

            # GBK 解码
            text = result.stdout.decode("gbk", errors="ignore")
            return self._parse_index_response(text)

        except subprocess.TimeoutExpired:
            logger.warning("curl 请求超时")
            return {}
        except FileNotFoundError:
            logger.warning("curl 命令不可用，尝试使用 requests")
            return self._fetch_with_requests(url)
        except Exception as e:
            logger.warning(f"腾讯指数数据获取失败: {e}")
            return {}

    def _fetch_with_requests(self, url: str) -> dict[str, Any]:
        """使用 requests 作为备用获取方式。"""
        try:
            session = requests.Session()
            session.trust_env = False
            session.headers.update({"User-Agent": "curl/8.7.1"})
            resp = session.get(url, timeout=self.timeout)
            text = resp.content.decode("gbk", errors="ignore")
            return self._parse_index_response(text)
        except Exception as e:
            logger.warning(f"requests 获取失败: {e}")
            return {}

    async def get_index_data_async(self) -> dict[str, Any]:
        """异步获取指数数据。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_index_data_sync)

    def _parse_index_response(self, text: str) -> dict[str, Any]:
        """解析腾讯指数响应。

        格式: v_s_sh000001="1~上证指数~000001~3957.05~-49.50~-1.24~..."
        """
        indices = {}

        for line in text.strip().split("\n"):
            match = re.search(r'v_(\w+)="([^"]+)"', line)
            if not match:
                continue

            code = match.group(1)
            data = match.group(2).split("~")

            if code not in self.INDEX_CODES:
                continue

            name, key = self.INDEX_CODES[code]
            try:
                # 腾讯指数格式: 1~名称~代码~当前价~涨跌额~涨跌幅~...
                current = float(data[3]) if len(data) > 3 and data[3] else 0
                change_pct = float(data[5]) if len(data) > 5 and data[5] else 0

                indices[key] = {
                    "name": name,
                    "close": current,
                    "change": change_pct / 100,  # 转换为小数
                }
            except (ValueError, IndexError):
                continue

        return indices


class FinanceClient:
    """财经数据客户端。

    使用多数据源策略：
    1. 腾讯财经（主要） - 稳定性好
    2. akshare/东方财富（备用）
    """

    DEFAULT_TIMEOUT = 30
    MAX_TIMEOUT = 60

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = min(timeout, self.MAX_TIMEOUT)
        self._semaphore = asyncio.Semaphore(2)
        self._tencent = TencentFinanceClient()
        self._eastmoney = EastMoneyCurlClient()

    async def _retry_request(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """带重试和超时控制的请求封装。"""
        async with self._semaphore:
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                        timeout=self.timeout,
                    )
                    return result
                except asyncio.TimeoutError:
                    last_error = TimeoutError(f"请求超时 ({self.timeout}秒)")
                    logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                except Exception as e:
                    last_error = e
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                    await asyncio.sleep(wait_time)

            raise FinanceAPIError(f"请求失败 (已重试 {self.max_retries} 次): {last_error}")

    async def get_index_data(self) -> dict[str, Any]:
        """获取 A 股主要指数数据。

        优先使用腾讯数据源，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用")
            return {}

        # 优先使用腾讯数据源
        try:
            indices = await self._tencent.get_index_data_async()
            if indices:
                logger.debug("使用腾讯数据源获取指数成功")
                return indices
        except Exception as e:
            logger.warning(f"腾讯数据源失败: {e}")

        # 回退到 akshare
        try:
            df = await self._retry_request(ak.stock_zh_index_spot_em)

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
                        "change": change_pct / 100,
                    }

            logger.debug("使用 akshare 数据源获取指数成功")
            return indices

        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return {}

    async def get_volume_data(self) -> dict[str, float]:
        """获取两市成交额数据。

        优先使用 curl 客户端，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

        # 优先使用 curl 客户端
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._eastmoney.get_stock_list)

            if data and "data" in data and "diff" in data["data"]:
                sh_volume = 0.0
                sz_volume = 0.0

                for item in data["data"]["diff"]:
                    code = str(item.get("f12", ""))
                    # f6 是成交额（元）
                    amount = float(item.get("f6", 0) or 0)

                    if code.startswith("6"):
                        sh_volume += amount
                    elif code.startswith(("0", "3")):
                        sz_volume += amount

                sh_volume = round(sh_volume / 1e8, 2)
                sz_volume = round(sz_volume / 1e8, 2)

                logger.debug(f"使用 curl 客户端获取成交额成功: 沪市 {sh_volume}亿, 深市 {sz_volume}亿")
                return {
                    "sh_volume": sh_volume,
                    "sz_volume": sz_volume,
                    "total_volume": round(sh_volume + sz_volume, 2),
                }
        except Exception as e:
            logger.warning(f"curl 客户端获取成交额失败: {e}")

        # 回退到 akshare
        try:
            df = await self._retry_request(ak.stock_zh_a_spot_em)

            sh_volume = 0.0
            sz_volume = 0.0

            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                amount = float(row.get("成交额", 0) or 0)

                if code.startswith("6"):
                    sh_volume += amount
                elif code.startswith(("0", "3")):
                    sz_volume += amount

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

        优先使用 curl 客户端，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}

        # 优先使用 curl 客户端
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._eastmoney.get_stock_list)

            if data and "data" in data and "diff" in data["data"]:
                up_count = 0
                down_count = 0
                flat_count = 0

                for item in data["data"]["diff"]:
                    # f3 是涨跌幅（百分比）
                    change = float(item.get("f3", 0) or 0)
                    if change > 0:
                        up_count += 1
                    elif change < 0:
                        down_count += 1
                    else:
                        flat_count += 1

                logger.debug(f"使用 curl 客户端获取涨跌统计成功: 上涨 {up_count}, 下跌 {down_count}")
                return {
                    "up_count": up_count,
                    "down_count": down_count,
                    "flat_count": flat_count,
                }
        except Exception as e:
            logger.warning(f"curl 客户端获取涨跌统计失败: {e}")

        # 回退到 akshare
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

        优先使用 curl 客户端，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return {"top_sectors": [], "bottom_sectors": []}

        # 优先使用 curl 客户端
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._eastmoney.get_board_list)

            if data and "data" in data and "diff" in data["data"]:
                # 按涨跌幅排序
                sectors = sorted(
                    data["data"]["diff"],
                    key=lambda x: float(x.get("f3", 0) or 0),
                    reverse=True,
                )

                top_sectors = []
                for item in sectors[:top_n]:
                    top_sectors.append({
                        "name": item.get("f14", ""),
                        "change": float(item.get("f3", 0) or 0) / 100,
                    })

                bottom_sectors = []
                for item in sectors[-top_n:]:
                    bottom_sectors.append({
                        "name": item.get("f14", ""),
                        "change": float(item.get("f3", 0) or 0) / 100,
                    })

                logger.debug(f"使用 curl 客户端获取板块数据成功")
                return {
                    "top_sectors": top_sectors,
                    "bottom_sectors": bottom_sectors,
                }
        except Exception as e:
            logger.warning(f"curl 客户端获取板块数据失败: {e}")

        # 回退到 akshare
        try:
            df = await self._retry_request(ak.stock_board_concept_name_em)
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

        优先使用 curl 客户端，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return []

        # 优先使用 curl 客户端
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._eastmoney.get_stock_list)

            if data and "data" in data and "diff" in data["data"]:
                # 筛选涨停股（涨跌幅 >= 9.9%）
                limit_up_stocks = [
                    item for item in data["data"]["diff"]
                    if float(item.get("f3", 0) or 0) >= 9.9
                ]

                # 按涨跌幅排序
                limit_up_stocks.sort(
                    key=lambda x: float(x.get("f3", 0) or 0),
                    reverse=True,
                )

                stocks = []
                for item in limit_up_stocks[:20]:
                    stocks.append({
                        "name": item.get("f14", ""),
                        "code": item.get("f12", ""),
                        "change": float(item.get("f3", 0) or 0) / 100,
                    })

                logger.debug(f"使用 curl 客户端获取涨停股成功: {len(stocks)} 只")
                return stocks
        except Exception as e:
            logger.warning(f"curl 客户端获取涨停股失败: {e}")

        # 回退到 akshare
        try:
            df = await self._retry_request(ak.stock_zh_a_spot_em)
            limit_up = df[df["涨跌幅"] >= 9.9].copy()

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
        """获取所有市场数据。"""
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用，返回空数据")
            return {
                "indices": {},
                "volume": {},
                "statistics": {},
                "sectors": {},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
            }

        logger.info("开始获取市场数据...")

        results = await asyncio.gather(
            self.get_index_data(),
            self.get_volume_data(),
            self.get_statistics(),
            self.get_sector_data(),
            self.get_limit_up_stocks(),
            return_exceptions=True,
        )

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
