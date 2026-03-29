"""财经数据 API 客户端 - 多数据源获取 A 股市场数据。

支持数据源：
- 腾讯财经 (主要) - 稳定性好
- 东方财富/akshare (备用)
"""

import ast
import asyncio
import contextlib
import inspect
import json
import logging
import math
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Optional

import akshare as ak
import httpx
import requests

logger = logging.getLogger(__name__)

# 是否禁用网络请求（用于测试或离线模式）
_DISABLE_NETWORK = os.environ.get("WCHAT_DISABLE_NETWORK", "").lower() in ("1", "true", "yes")

# 缓存配置
_CACHE_TTL_SECONDS = 300  # 5 分钟缓存


@contextlib.contextmanager
def _silence_tqdm():
    """临时禁用 tqdm 进度条，避免第三方库（如 akshare）内部分页进度污染 CLI 输出。"""
    old = os.environ.get("TQDM_DISABLE")
    os.environ["TQDM_DISABLE"] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = old


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

            data = self._parse_response_text(text)
            if not isinstance(data, dict):
                logger.warning(f"curl 返回了非对象响应: {type(data).__name__}")
                return None
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

    def _parse_response_text(self, text: str) -> Any:
        """解析 curl 返回文本，优先按 JSON 解析，必要时回退到 Python 字面量。"""
        stripped = text.strip()
        if not stripped:
            return None

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return ast.literal_eval(stripped)

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
    SOURCE_STRATEGIES: dict[str, tuple[str, ...]] = {
        "indices": ("tencent_realtime", "akshare_index_spot"),
        "snapshot": ("eastmoney_stock_snapshot", "akshare_a_spot"),
        "sectors": (
            "akshare_sector_spot",
            "akshare_board_concept_name_em",
            "eastmoney_board_list",
        ),
        "limit_up": (
            "akshare_zt_pool_em",
            "eastmoney_snapshot_filter",
            "akshare_a_spot_filter",
        ),
    }

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

    async def _run_source_strategy(
        self,
        data_type: str,
        adapters: list[tuple[str, Any]],
        is_success: Any,
    ) -> Any:
        """按声明顺序执行某类数据的 source strategy。"""
        for name, adapter in adapters:
            try:
                result = adapter()
                if inspect.isawaitable(result):
                    result = await result
                if is_success(result):
                    logger.debug("市场数据源命中: %s -> %s", data_type, name)
                    return result
            except Exception as e:
                logger.warning("%s 数据源 %s 失败: %s", data_type, name, e)
        return None

    def _to_float(self, value: Any) -> float | None:
        """尽量将值转换为有限浮点数。"""
        if value in (None, ""):
            return None
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(result):
            return None
        return result

    def _normalize_pct(self, value: Any) -> float | None:
        """将百分数口径统一转换为小数。"""
        raw = self._to_float(value)
        if raw is None:
            return None
        return raw / 100

    def _normalize_sector_rows(self, rows: list[dict[str, Any]], top_n: int = 5) -> dict[str, list]:
        """将不同板块源的记录统一为 contract。"""
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            name = str(
                item.get("板块")
                or item.get("板块名称")
                or item.get("名称")
                or item.get("name")
                or item.get("f14")
                or ""
            )
            if not name:
                continue
            change = self._normalize_pct(item.get("涨跌幅", item.get("change", item.get("f3"))))
            if change is None:
                continue
            code = str(item.get("代码") or item.get("板块代码") or item.get("code") or item.get("f12") or "")
            normalized.append({"name": name, "code": code, "change": change})

        if not normalized:
            return {"top_sectors": [], "bottom_sectors": []}

        sorted_rows = sorted(normalized, key=lambda x: x["change"], reverse=True)
        return {
            "top_sectors": sorted_rows[:top_n],
            "bottom_sectors": sorted_rows[-top_n:],
        }

    def _normalize_limit_up_rows(self, rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
        """将不同涨停股源的记录统一为 contract。"""
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            code = str(item.get("代码") or item.get("code") or item.get("f12") or "")
            name = str(item.get("名称") or item.get("name") or item.get("f14") or "")
            change = self._normalize_pct(item.get("涨跌幅", item.get("change", item.get("f3"))))
            if not code or not name or change is None:
                continue
            stock: dict[str, Any] = {"name": name, "code": code, "change": change}
            limit_days = item.get("连板数") or item.get("limit_days")
            industry = item.get("所属行业") or item.get("industry")
            if limit_days not in (None, ""):
                try:
                    stock["limit_days"] = int(limit_days)
                except (TypeError, ValueError):
                    pass
            if industry:
                stock["industry"] = str(industry)
            normalized.append(stock)

        normalized.sort(key=lambda x: x["change"], reverse=True)
        return normalized[:limit]

    def _records_from_dataframe(self, data: Any) -> list[dict[str, Any]]:
        """从 dataframe 风格对象提取 records，并拒绝协程式 mock。"""
        to_dict = getattr(data, "to_dict", None)
        if not callable(to_dict) or inspect.iscoroutinefunction(to_dict):
            raise ValueError("adapter did not return a dataframe-like object")
        records = to_dict("records")
        if not isinstance(records, list):
            raise ValueError("dataframe-like object returned non-list records")
        return records

    async def _get_index_data_from_tencent(self) -> dict[str, Any]:
        return await self._tencent.get_index_data_async()

    async def _get_index_data_from_akshare(self) -> dict[str, Any]:
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
        return indices

    async def _get_sector_data_from_stock_sector_spot(self, top_n: int = 5) -> dict[str, list]:
        df = await self._retry_request(ak.stock_sector_spot, indicator="概念")
        rows = self._records_from_dataframe(df)
        return self._normalize_sector_rows(rows, top_n=top_n)

    async def _get_sector_data_from_board_name_em(self, top_n: int = 5) -> dict[str, list]:
        df = await self._retry_request(ak.stock_board_concept_name_em)
        rows = self._records_from_dataframe(df)
        return self._normalize_sector_rows(rows, top_n=top_n)

    async def _get_sector_data_from_eastmoney(self, top_n: int = 5) -> dict[str, list]:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._eastmoney.get_board_list)
        stocks = self._normalize_stock_snapshot({"data": {"diff": data.get("data", {}).get("diff", [])}}) if isinstance(data, Mapping) else []
        return self._normalize_sector_rows(stocks, top_n=top_n)

    def _format_trade_date_for_zt_pool(self, trade_date: date | datetime | None) -> str:
        base = trade_date.date() if isinstance(trade_date, datetime) else trade_date
        if base is None:
            base = date.today()
        return base.strftime("%Y%m%d")

    async def _get_limit_up_from_zt_pool(self, trade_date: date | datetime | None = None) -> list[dict[str, Any]]:
        df = await self._retry_request(
            ak.stock_zt_pool_em,
            date=self._format_trade_date_for_zt_pool(trade_date),
        )
        return self._normalize_limit_up_rows(self._records_from_dataframe(df))

    async def _get_limit_up_from_snapshot(self) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._eastmoney.get_stock_list)
        stocks = self._normalize_stock_snapshot(data)
        limit_up_rows = [
            item for item in stocks
            if (self._to_float(item.get("f3")) or 0) >= 9.9
        ]
        return self._normalize_limit_up_rows(limit_up_rows)

    async def _get_limit_up_from_spot_em(self) -> list[dict[str, Any]]:
        df = await self._retry_request(ak.stock_zh_a_spot_em)
        rows = [
            row.to_dict()
            for _, row in df[df["涨跌幅"] >= 9.9].head(20).iterrows()
        ]
        return self._normalize_limit_up_rows(rows)

    async def _get_volume_data_from_spot_em(self) -> dict[str, float]:
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

    async def _get_statistics_from_spot_em(self) -> dict[str, int]:
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

    async def _fetch_spot_em_dataframe(self) -> Any:
        """获取 akshare 全市场 A 股快照 DataFrame（单次获取，供成交额和涨跌统计共享）。"""
        return await self._retry_request(ak.stock_zh_a_spot_em)

    def _compute_volume_from_spot_em_df(self, df: Any) -> dict[str, float]:
        """从 akshare 全市场 DataFrame 计算两市成交额。"""
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

    def _compute_statistics_from_spot_em_df(self, df: Any) -> dict[str, int]:
        """从 akshare 全市场 DataFrame 计算涨跌统计。"""
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

    async def _retry_request(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """带重试、超时控制和进度静默的请求封装。"""
        with _silence_tqdm():
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

    async def _fetch_stock_snapshot(self) -> tuple[list[dict], dict[str, Any]]:
        """获取全市场股票快照（分页聚合，供成交额和涨跌统计共享）。

        Returns:
            (stocks, quality) 元组:
            - stocks: 股票快照列表
            - quality: {"status": "ok"|"partial"|"error", "source": str,
                        "actual_count": int, "expected_count": int}
        """
        error_quality: dict[str, Any] = {
            "status": "error", "source": "eastmoney_curl",
            "actual_count": 0, "expected_count": 0,
        }

        if _DISABLE_NETWORK:
            return [], error_quality

        try:
            loop = asyncio.get_event_loop()

            # 首页请求，获取 total 和第一批数据
            first_page = await loop.run_in_executor(
                None, lambda: self._eastmoney.get_stock_list(page=1, page_size=5000)
            )

            all_stocks = self._normalize_stock_snapshot(first_page)

            # 从首页获取 expected_count
            expected_count = 0
            if isinstance(first_page, Mapping):
                payload = first_page.get("data")
                if isinstance(payload, Mapping):
                    expected_count = int(payload.get("total", 0) or 0)

            # 首页请求完全失败（返回 None 或非 dict），视为 error
            if not isinstance(first_page, Mapping):
                error_quality["expected_count"] = 0
                return [], error_quality

            # 首页已包含全部数据
            if expected_count == 0 or len(all_stocks) >= expected_count:
                status = "ok"
                quality: dict[str, Any] = {
                    "status": status, "source": "eastmoney_curl",
                    "actual_count": len(all_stocks),
                    "expected_count": expected_count,
                }
                logger.debug(
                    "全市场股票快照: %s/%s (%s)", len(all_stocks), expected_count, status
                )
                return all_stocks, quality

            # 基于首页实际返回条数推导分页需求
            first_page_count = len(all_stocks)
            if first_page_count <= 0:
                status = "partial"
                quality = {
                    "status": status, "source": "eastmoney_curl",
                    "actual_count": 0, "expected_count": expected_count,
                }
                logger.debug(
                    "全市场股票快照: 首页返回空 (%s/%s)", 0, expected_count
                )
                return [], quality

            # 按 f12 去重，以唯一股票数判定完整性
            seen_codes: dict[str, dict[str, Any]] = {
                s.get("f12", ""): s for s in all_stocks if s.get("f12")
            }

            # 动态最大页数 = 理论页数 + 2 页余量（防漂移），上限 200 页
            theoretical_pages = math.ceil(expected_count / first_page_count)
            max_pages = min(theoretical_pages + 2, 200)

            page = 2
            consecutive_empty = 0
            while len(seen_codes) < expected_count and page <= max_pages:
                page_data = await loop.run_in_executor(
                    None, lambda p=page: self._eastmoney.get_stock_list(page=p, page_size=5000)
                )
                page_stocks = self._normalize_stock_snapshot(page_data)
                if not page_stocks:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page += 1
                    continue

                consecutive_empty = 0
                prev_count = len(seen_codes)
                for s in page_stocks:
                    code = s.get("f12", "")
                    if code and code not in seen_codes:
                        seen_codes[code] = s
                # 无新增记录 → 短路退出
                if len(seen_codes) == prev_count:
                    break
                page += 1

            unique_stocks = list(seen_codes.values())
            actual_count = len(unique_stocks)
            status = "ok" if actual_count >= expected_count else "partial"
            quality = {
                "status": status, "source": "eastmoney_curl",
                "actual_count": actual_count,
                "expected_count": expected_count,
            }
            logger.debug(
                "全市场股票快照(分页): %s/%s (%s, %s页)",
                actual_count, expected_count, status, page - 1,
            )
            return unique_stocks, quality

        except Exception as e:
            logger.warning(f"获取全市场股票快照失败: {e}")
            return [], error_quality

    def _normalize_stock_snapshot(self, data: Any) -> list[dict[str, Any]]:
        """从上游响应中提取可用的股票列表，只保留字典项。

        兼容 data.diff 为 list 或 dict（东方财富上游结构已从 list 变为按序号索引的 dict）。
        """
        if not isinstance(data, Mapping):
            return []

        payload = data.get("data")
        if not isinstance(payload, Mapping):
            return []

        diff = payload.get("diff")
        if not diff:
            return []

        # 兼容 list 和 dict 两种格式
        if isinstance(diff, dict):
            items = list(diff.values())
        elif isinstance(diff, list):
            items = diff
        else:
            return []

        normalized = [dict(item) for item in items if isinstance(item, Mapping)]
        if len(normalized) != len(items):
            logger.warning(
                "股票快照包含非对象项，已忽略: total=%s valid=%s",
                len(items),
                len(normalized),
            )
        return normalized

    def compute_volume_data(self, stocks: list[dict]) -> dict[str, float]:
        """基于已有股票快照计算两市成交额。"""
        if not stocks:
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

        sh_volume = 0.0
        sz_volume = 0.0

        for item in stocks:
            if not isinstance(item, Mapping):
                continue
            try:
                code = str(item.get("f12", ""))
                amount = float(item.get("f6", 0) or 0)
            except (TypeError, ValueError):
                continue

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

    def compute_statistics(self, stocks: list[dict]) -> dict[str, int]:
        """基于已有股票快照计算涨跌统计。"""
        if not stocks:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}

        up_count = 0
        down_count = 0
        flat_count = 0

        for item in stocks:
            if not isinstance(item, Mapping):
                continue
            try:
                change = float(item.get("f3", 0) or 0)
            except (TypeError, ValueError):
                continue
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

    async def get_index_data(self) -> dict[str, Any]:
        """获取 A 股主要指数数据。

        优先使用腾讯数据源，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用")
            return {}
        adapters = [
            (self.SOURCE_STRATEGIES["indices"][0], self._get_index_data_from_tencent),
            (self.SOURCE_STRATEGIES["indices"][1], self._get_index_data_from_akshare),
        ]
        result = await self._run_source_strategy("indices", adapters, lambda data: bool(data))
        return result or {}

    async def get_volume_data(self, stocks: list[dict] | None = None) -> dict[str, float]:
        """获取两市成交额数据。

        优先使用全市场快照计算，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

        try:
            if stocks is None:
                stocks, _ = await self._fetch_stock_snapshot()
        except Exception as e:
            logger.warning(f"全市场快照获取失败，成交额切换备用源: {e}")
            stocks = []
        volume_data = await self._run_source_strategy(
            "volume",
            [
                (
                    self.SOURCE_STRATEGIES["snapshot"][0],
                    lambda: self.compute_volume_data(stocks) if stocks else None,
                ),
                (self.SOURCE_STRATEGIES["snapshot"][1], self._get_volume_data_from_spot_em),
            ],
            lambda data: bool(data and all(key in data for key in ("sh_volume", "sz_volume", "total_volume"))),
        )
        return volume_data or {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    async def get_statistics(self, stocks: list[dict] | None = None) -> dict[str, int]:
        """获取涨跌统计数据。

        优先使用全市场快照计算，失败时回退到 akshare。
        """
        if _DISABLE_NETWORK:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}

        try:
            if stocks is None:
                stocks, _ = await self._fetch_stock_snapshot()
        except Exception as e:
            logger.warning(f"全市场快照获取失败，涨跌统计切换备用源: {e}")
            stocks = []
        stats = await self._run_source_strategy(
            "statistics",
            [
                (
                    self.SOURCE_STRATEGIES["snapshot"][0],
                    lambda: self.compute_statistics(stocks) if stocks else None,
                ),
                (self.SOURCE_STRATEGIES["snapshot"][1], self._get_statistics_from_spot_em),
            ],
            lambda data: bool(data and all(key in data for key in ("up_count", "down_count", "flat_count"))),
        )
        return stats or {"up_count": 0, "down_count": 0, "flat_count": 0}

    async def get_sector_data(self, top_n: int = 5) -> dict[str, list]:
        """获取板块涨跌数据。

        优先使用专用板块 adapter，失败时按策略降级。
        """
        if _DISABLE_NETWORK:
            return {"top_sectors": [], "bottom_sectors": []}

        adapters = [
            (self.SOURCE_STRATEGIES["sectors"][0], lambda: self._get_sector_data_from_stock_sector_spot(top_n=top_n)),
            (self.SOURCE_STRATEGIES["sectors"][1], lambda: self._get_sector_data_from_board_name_em(top_n=top_n)),
            (self.SOURCE_STRATEGIES["sectors"][2], lambda: self._get_sector_data_from_eastmoney(top_n=top_n)),
        ]
        result = await self._run_source_strategy(
            "sectors",
            adapters,
            lambda data: bool(data and (data.get("top_sectors") or data.get("bottom_sectors"))),
        )
        return result or {"top_sectors": [], "bottom_sectors": []}

    async def get_limit_up_stocks(self, min_days: int = 2, trade_date: Optional[date | datetime] = None) -> list[dict[str, Any]]:
        """获取连板个股数据。

        优先使用专用涨停池 adapter，失败时按策略降级。
        """
        if _DISABLE_NETWORK:
            return []

        adapters = [
            (self.SOURCE_STRATEGIES["limit_up"][0], lambda: self._get_limit_up_from_zt_pool(trade_date=trade_date)),
            (self.SOURCE_STRATEGIES["limit_up"][1], self._get_limit_up_from_snapshot),
            (self.SOURCE_STRATEGIES["limit_up"][2], self._get_limit_up_from_spot_em),
        ]
        result = await self._run_source_strategy(
            "limit_up",
            adapters,
            lambda data: data is not None,
        )
        return result or []

    def _determine_breadth_quality(
        self,
        snapshot_quality: dict[str, Any],
        result_data: dict[str, Any],
        data_type: str,
    ) -> dict[str, Any]:
        """基于快照质量和最终结果确定宽度数据质量。"""
        if snapshot_quality["status"] == "ok":
            return {
                "status": "ok",
                "source": snapshot_quality["source"],
                "actual_count": snapshot_quality["actual_count"],
                "expected_count": snapshot_quality["expected_count"],
            }

        # 快照不完整或失败，检查备用源是否成功
        if data_type == "volume":
            has_data = result_data.get("total_volume", 0) > 0
        else:
            has_data = (
                result_data.get("up_count", 0)
                + result_data.get("down_count", 0)
                + result_data.get("flat_count", 0)
            ) > 0

        if has_data:
            return {
                "status": "ok",
                "source": "akshare_spot_em",
                "actual_count": 0,
                "expected_count": snapshot_quality.get("expected_count", 0),
            }

        return {
            "status": snapshot_quality["status"],
            "source": snapshot_quality["source"],
            "actual_count": snapshot_quality["actual_count"],
            "expected_count": snapshot_quality.get("expected_count", 0),
        }

    async def get_all_market_data(self, trade_date: Optional[date | datetime] = None) -> dict[str, Any]:
        """获取所有市场数据。

        成交额和涨跌统计基于同一轮全市场股票快照计算，避免重复抓取。
        快照不完整时自动降级到备用源，并在返回结果中附带宽度数据质量状态。
        """
        if _DISABLE_NETWORK:
            logger.warning("网络请求已禁用，返回空数据")
            return {
                "indices": {},
                "volume": {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
                "statistics": {"up_count": 0, "down_count": 0, "flat_count": 0},
                "sectors": {"top_sectors": [], "bottom_sectors": []},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
                "breadth_quality": {
                    "volume": {"status": "error", "source": "disabled", "actual_count": 0, "expected_count": 0},
                    "statistics": {"status": "error", "source": "disabled", "actual_count": 0, "expected_count": 0},
                },
            }

        logger.info("开始获取市场数据...")

        # 并行：获取快照 + 其他不依赖快照的数据
        (stock_snapshot, snapshot_quality), other_results = await asyncio.gather(
            self._fetch_stock_snapshot(),
            asyncio.gather(
                self.get_index_data(),
                self.get_sector_data(),
                self.get_limit_up_stocks(trade_date=trade_date),
                return_exceptions=True,
            ),
        )

        # 基于快照质量决定成交额和涨跌统计的获取路径
        if snapshot_quality["status"] == "ok":
            volume = self.compute_volume_data(stock_snapshot)
            statistics = self.compute_statistics(stock_snapshot)
        else:
            # 快照不完整/失败，使用共享备用快照（一次 akshare 抓取，同时计算成交额和涨跌统计）
            logger.info("快照不完整(%s)，尝试共享备用源获取成交额和涨跌统计", snapshot_quality["status"])
            try:
                spot_df = await self._fetch_spot_em_dataframe()
                volume = self._compute_volume_from_spot_em_df(spot_df)
                statistics = self._compute_statistics_from_spot_em_df(spot_df)
            except Exception as e:
                logger.warning("共享备用源获取失败: %s", e)
                volume = {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}
                statistics = {"up_count": 0, "down_count": 0, "flat_count": 0}

        breadth_quality = {
            "volume": self._determine_breadth_quality(snapshot_quality, volume, "volume"),
            "statistics": self._determine_breadth_quality(snapshot_quality, statistics, "statistics"),
        }

        market_data = {
            "indices": other_results[0] if not isinstance(other_results[0], Exception) else {},
            "volume": volume,
            "statistics": statistics,
            "sectors": other_results[1] if not isinstance(other_results[1], Exception) else {},
            "limit_up": other_results[2] if not isinstance(other_results[2], Exception) else [],
            "fetch_time": datetime.now().isoformat(),
            "breadth_quality": breadth_quality,
        }

        logger.info("市场数据获取完成")
        return market_data
