"""财联社看盘数据 API 客户端。

支持获取实时市场热点数据，包括个股点评、题材板块等信息。
"""

import hashlib
import json
import logging
import subprocess
import time
from datetime import datetime
from threading import Lock
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# 是否禁用网络请求（用于测试或离线模式）
_DISABLE_NETWORK = False

# API 配置
CLS_WATCH_URL = "https://www.cls.cn/v1/roll/get_roll_list"
CLS_APP_NAME = "CailianpressWeb"
CLS_OS = "web"
CLS_SV = "8.4.6"
CLS_CATEGORY_WATCH = "watch"


def generate_sign(params: dict[str, Any]) -> str:
    """生成财联社 API 签名。

    签名算法:
    1. 对参数按键名排序
    2. URL 编码生成查询字符串
    3. 对查询字符串计算 SHA1 哈希
    4. 对 SHA1 结果计算 MD5 哈希

    Args:
        params: API 请求参数（不含 sign）

    Returns:
        签名字符串
    """
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params)
    sha1_hash = hashlib.sha1(query_string.encode()).hexdigest()
    sign = hashlib.md5(sha1_hash.encode()).hexdigest()
    return sign


class CLSWatchClient:
    """财联社看盘数据 API 客户端。

    支持获取市场热点数据（股票、题材、板块点评等）。
    优先使用 httpx，失败时降级到 curl。
    """

    # 每页默认返回条数
    DEFAULT_PAGE_SIZE = 20

    # 请求间隔（秒），避免触发速率限制
    REQUEST_INTERVAL = 0.5

    def __init__(self, timeout: float = 10.0):
        """初始化客户端。

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self._cache: dict[str, Any] = {}
        self._cache_time: Optional[float] = None
        self._lock = Lock()
        self._last_request_time: float = 0

    def _build_params(
        self,
        last_time: int,
        category: str = CLS_CATEGORY_WATCH,
        rn: int = DEFAULT_PAGE_SIZE,
        refresh_type: int = 1,
    ) -> dict[str, str]:
        """构建 API 请求参数。

        Args:
            last_time: Unix 时间戳，返回早于该时间的记录
            category: 分类标识
            rn: 每页条数
            refresh_type: 1 = 加载更多

        Returns:
            包含签名的参数字典
        """
        params = {
            "app": CLS_APP_NAME,
            "category": category,
            "last_time": str(last_time),
            "os": CLS_OS,
            "refresh_type": str(refresh_type),
            "rn": str(rn),
            "sv": CLS_SV,
        }
        params["sign"] = generate_sign(params)
        return params

    def _rate_limit(self) -> None:
        """速率限制，确保请求间隔。"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _fetch_with_httpx(self, params: dict[str, str]) -> Optional[dict]:
        """使用 httpx 获取数据。"""
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用")
            return None

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.cls.cn/",
            }

            # trust_env=False 禁用系统代理，verify=False 跳过 SSL 验证
            with httpx.Client(timeout=self.timeout, trust_env=False, verify=False) as client:
                response = client.get(CLS_WATCH_URL, params=params, headers=headers)

                if response.status_code != 200:
                    logger.warning(f"httpx 请求失败: {response.status_code}")
                    return None

                return response.json()

        except Exception as e:
            logger.debug(f"httpx 请求异常: {e}")
            return None

    def _fetch_with_curl(self, params: dict[str, str]) -> Optional[dict]:
        """使用 curl 获取数据（作为 httpx 的降级方案）。"""
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用")
            return None

        try:
            query_string = urlencode(sorted(params.items()))
            url = f"{CLS_WATCH_URL}?{query_string}"

            result = subprocess.run(
                [
                    "curl", "-s", "-k", "--noproxy", "*",
                    "--connect-timeout", str(int(self.timeout)),
                    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "-H", "Referer: https://www.cls.cn/",
                    url
                ],
                capture_output=True,
                text=False,
                timeout=self.timeout + 5,
            )

            if result.returncode != 0:
                logger.warning(f"curl 失败 (code {result.returncode})")
                return None

            text = result.stdout.decode("utf-8", errors="ignore")
            if not text:
                logger.warning("curl 返回空响应")
                return None

            return json.loads(text)

        except subprocess.TimeoutExpired:
            logger.warning("curl 请求超时")
            return None
        except FileNotFoundError:
            logger.warning("curl 命令不可用")
            return None
        except Exception as e:
            logger.warning(f"curl 请求失败: {e}")
            return None

    def _fetch_page(
        self,
        last_time: int,
        category: str = CLS_CATEGORY_WATCH,
        rn: int = DEFAULT_PAGE_SIZE
    ) -> list[dict[str, Any]]:
        """获取单页数据。

        Args:
            last_time: Unix 时间戳
            category: 分类标识
            rn: 每页条数

        Returns:
            看盘数据列表
        """
        self._rate_limit()

        params = self._build_params(last_time, category, rn)

        # 优先使用 httpx
        data = self._fetch_with_httpx(params)

        # 降级到 curl
        if data is None:
            logger.debug("httpx 失败，尝试 curl")
            data = self._fetch_with_curl(params)

        if data is None:
            return []

        # 解析响应
        if data.get("errno") != 0:
            logger.warning(f"API 返回错误: {data.get('errmsg', 'unknown')}")
            return []

        roll_data = data.get("data", {}).get("roll_data", [])
        return roll_data if roll_data else []

    def fetch_hot_data(self, limit: int = 20, category: str = CLS_CATEGORY_WATCH) -> list[dict[str, Any]]:
        """获取最新热点数据。

        Args:
            limit: 返回条数，默认 20
            category: 分类标识

        Returns:
            热点数据列表，每条包含:
                - title: 标题
                - content: 内容
                - ctime: 发布时间戳
                - stocks: 关联股票列表
                - sectors: 关联板块列表
        """
        current_time = int(time.time())
        return self._fetch_page(current_time, category, rn=limit)

    def fetch_by_time_range(
        self,
        start_time: int,
        end_time: int,
        category: str = CLS_CATEGORY_WATCH,
        progress_callback: Optional[callable] = None,
    ) -> list[dict[str, Any]]:
        """按时间范围获取看盘数据。

        使用分页循环拉取，直到获取完所有数据。

        Args:
            start_time: 开始时间（Unix 时间戳）
            end_time: 结束时间（Unix 时间戳）
            category: 分类标识
            progress_callback: 进度回调函数，参数为 (fetched_count, has_more)

        Returns:
            看盘数据列表
        """
        all_items: list[dict[str, Any]] = []
        current_time = end_time
        fetched_count = 0

        while current_time > start_time:
            items = self._fetch_page(current_time, category, rn=self.DEFAULT_PAGE_SIZE)

            if not items:
                break

            # 过滤时间范围
            filtered = [
                item for item in items
                if start_time <= item.get("ctime", 0) <= end_time
            ]

            all_items.extend(filtered)
            fetched_count += len(items)

            # 获取最早的时间作为下次请求的 last_time
            min_ctime = min(item.get("ctime", 0) for item in items)
            if min_ctime <= 0 or min_ctime >= current_time:
                break

            current_time = min_ctime - 1

            # 回调进度
            if progress_callback:
                progress_callback(fetched_count, current_time > start_time)

            # 如果最早的数据已经早于 start_time，停止
            if min_ctime < start_time:
                break

        # 按时间排序（最新的在前）
        all_items.sort(key=lambda x: x.get("ctime", 0), reverse=True)

        return all_items

    def parse_watch_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """解析单条看盘数据。

        Args:
            item: 原始看盘数据

        Returns:
            解析后的数据:
                - watch_id: 唯一标识
                - title: 标题
                - content: 内容
                - publish_time: 发布时间 (datetime)
                - ctime: 发布时间戳
                - data_type: 数据类型
                - stocks: 股票列表
                - sectors: 板块列表
        """
        ctime = item.get("ctime", 0)
        publish_time = datetime.fromtimestamp(ctime) if ctime else None

        # 提取股票和板块信息
        stocks = item.get("stocks", [])
        sectors = item.get("sectors", [])

        # 确定数据类型
        data_type = "hot"  # 默认为热点数据
        if stocks or sectors:
            data_type = "stock_comment"  # 个股点评

        return {
            "watch_id": str(item.get("id", "")),
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "publish_time": publish_time,
            "ctime": ctime,
            "data_type": data_type,
            "stocks": stocks if isinstance(stocks, list) else [],
            "sectors": sectors if isinstance(sectors, list) else [],
        }
