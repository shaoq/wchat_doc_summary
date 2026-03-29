"""板块数据 API 客户端 - 使用同花顺数据源。

通过 curl 命令获取同花顺行业板块页面，解析 HTML 表格提取板块数据。
"""

import logging
import os
import re
import subprocess
import time
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional

from src.models.schema import SectorData

logger = logging.getLogger(__name__)

def _is_network_disabled() -> bool:
    """检查网络请求是否被禁用（每次调用时检查环境变量）. """
    return os.environ.get("WCHAT_DISABLE_NETWORK", "").lower() in ("1", "true", "yes")

# 缓存配置
_CACHE_TTL_SECONDS = 300  # 5 分钟缓存


class SectorAPIError(Exception):
    """板块 API 错误。"""
    pass


def cached(func: Callable) -> Callable:
    """缓存装饰器 - 缓存函数返回值 5 分钟。"""
    @wraps(func)
    def wrapper(self: "THSSectorClient", *args, **kwargs):
        # 检查缓存
        cache_key = func.__name__
        if hasattr(self, '_cache') and hasattr(self, '_cache_time'):
            with self._lock:
                if self._is_cache_valid(cache_key):
                    logger.debug(f"使用缓存的 {cache_key} 数据")
                    return self._cache.get(cache_key, [])

        # 调用原函数
        result = func(self, *args, **kwargs)

        # 更新缓存
        if hasattr(self, '_cache') and result:
            with self._lock:
                self._cache[cache_key] = result
                self._cache_time[cache_key] = time.time()

        return result
    return wrapper


class THSSectorClient:
    """同花顺板块数据客户端。

    通过 curl 命令获取同花顺行业板块页面，解析 HTML 表格提取数据。

    API 端点：
    - 行业板块：http://q.10jqka.com.cn/thshy/
    - 概念板块：暂不支持（需要 JavaScript 渲染）

    数据字段：
    - 板块名称
    - 涨跌幅
    - 总成交量
    - 总成交额
    """

    # API 端点
    INDUSTRY_URL = "http://q.10jqka.com.cn/thshy/"
    CONCEPT_URL = "http://q.10jqka.com.cn/gn/"

    def __init__(self, timeout: float = 10.0):
        """初始化板块客户端。

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self._cache: dict[str, Any] = {}
        self._cache_time: dict[str, float] = {}
        self._lock = Lock()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效。"""
        if cache_key not in self._cache_time:
            return False
        return (time.time() - self._cache_time[cache_key]) < _CACHE_TTL_SECONDS

    def _fetch_with_curl(self, url: str) -> Optional[str]:
        """使用 curl 获取页面内容。

        Args:
            url: 请求 URL

        Returns:
            页面 HTML 内容，失败时返回 None
        """
        if _is_network_disabled():
            logger.warning("网络请求已禁用")
            return None

        try:
            result = subprocess.run(
                [
                    "curl", "-s", "-k", "--noproxy", "*",
                    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "-H", "Referer: http://q.10jqka.com.cn/",
                    "--connect-timeout", str(int(self.timeout)),
                    url
                ],
                capture_output=True,
                text=False,
                timeout=self.timeout + 5,
            )

            if result.returncode != 0:
                logger.warning(f"curl 失败 (code {result.returncode}): {result.stderr.decode('utf-8', errors='ignore')}")
                return None

            text = result.stdout.decode("gbk", errors="ignore")
            if not text:
                logger.warning("curl 返回空响应")
                return None

            return text

        except subprocess.TimeoutExpired:
            logger.warning("curl 请求超时")
            return None
        except FileNotFoundError:
            logger.warning("curl 命令不可用")
            return None
        except Exception as e:
            logger.warning(f"curl 获取失败: {e}")
            return None

    def _parse_industry_table(self, html: str) -> list[SectorData]:
        """解析同花顺行业板块表格。

        表格结构：
        | 序号 | 板块 | 涨跌幅(%) | 总成交量（万手） | 总成交额（亿元） | ...

        Args:
            html: 页面 HTML 内容

        Returns:
            解析后的板块数据列表
        """
        sectors = []

        try:
            # 查找表格 - 同花顺使用 bdbox 类
            table_match = re.search(
                r'<table[^>]*class=["\'][^"\']*bdbox[^"\']*["\'][^>]*>(.*?)</table>',
                html, re.DOTALL
            )
            if not table_match:
                # 备用：查找 tbody
                table_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.DOTALL)

            if not table_match:
                logger.warning("未找到板块数据表格")
                return []

            table = table_match.group(1)
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)

            for row in rows[1:]:  # 跳过表头
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cells) >= 5:
                    # 提取板块名称（在第 2 列，通常是链接）
                    name_match = re.search(r'>([^<]+)</a>', cells[1])
                    if not name_match:
                        name_match = re.search(r'>([^<]+)<', cells[1])
                    sector_name = name_match.group(1).strip() if name_match else ""

                    # 提取涨跌幅（在第 3 列）
                    change_text = re.sub(r'<[^>]+>', '', cells[2]).strip()
                    try:
                        change_pct = float(change_text)
                    except ValueError:
                        change_pct = 0.0

                    # 提取成交量（在第 4 列，万手）
                    volume_text = re.sub(r'<[^>]+>', '', cells[3]).strip()
                    try:
                        volume = float(volume_text) * 10000  # 转换为手
                    except ValueError:
                        volume = 0

                    # 提取成交额（在第 5 列，亿元）
                    amount_text = re.sub(r'<[^>]+>', '', cells[4]).strip()
                    try:
                        amount = float(amount_text) * 100000000  # 转换为元
                    except ValueError:
                        amount = 0

                    if sector_name:
                        sectors.append(SectorData(
                            code="",  # 同花顺页面无板块代码
                            name=sector_name,
                            change_pct=change_pct,
                            volume=volume,
                            amount=amount,
                        ))

        except Exception as e:
            logger.error(f"解析板块数据失败: {e}")

        logger.debug(f"解析板块数据成功，共 {len(sectors)} 条")
        return sectors

    @cached
    def get_industry_sectors(self, limit: Optional[int] = None) -> list[SectorData]:
        """获取行业板块列表。

        从同花顺获取行业板块数据，按涨跌幅降序排列。

        Args:
            limit: 返回条数限制，None 表示返回全部

        Returns:
            行业板块数据列表
        """
        html = self._fetch_with_curl(self.INDUSTRY_URL)
        if not html:
            logger.warning("获取行业板块页面失败")
            return []

        sectors = self._parse_industry_table(html)

        # 按涨跌幅降序排列
        sectors.sort(key=lambda x: x.change_pct or 0, reverse=True)

        if limit:
            return sectors[:limit]
        return sectors

    @cached
    def get_concept_sectors(self, limit: Optional[int] = None) -> list[SectorData]:
        """获取概念板块列表。

        注意：同花顺概念板块页面需要 JavaScript 渲染，暂不支持。
        返回空列表以保持接口兼容。

        Args:
            limit: 返回条数限制

        Returns:
            空列表（暂不支持）
        """
        logger.warning("同花顺概念板块暂不支持（需要 JavaScript 渲染）")
        return []

    def clear_cache(self) -> None:
        """清除所有缓存。"""
        with self._lock:
            self._cache = {}
            self._cache_time = {}
        logger.debug("板块缓存已清除")


# 保持向后兼容的别名
SectorClient = THSSectorClient
