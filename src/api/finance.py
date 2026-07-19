"""财经数据 API 客户端 - 多数据源获取 A 股市场数据。

支持数据源：
- 腾讯财经 (主要) - 稳定性好
- 东方财富/akshare (备用)
"""

import ast
import asyncio
import contextlib
import csv
import inspect
import json
import logging
import math
import os
import re
import subprocess
from collections.abc import Mapping
from datetime import date, datetime, time as time_type
from enum import Enum
from typing import Any, Optional, TypedDict
from zoneinfo import ZoneInfo

import akshare as ak
import httpx
import requests

logger = logging.getLogger(__name__)

# 是否禁用网络请求（用于测试或离线模式）
_DISABLE_NETWORK = os.environ.get("WCHAT_DISABLE_NETWORK", "").lower() in ("1", "true", "yes")


class ProviderFailureType(str, Enum):
    """海外市场上下文 provider 失败分类。"""

    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    EMPTY = "empty"
    MALFORMED = "malformed"
    NETWORK_ERROR = "network_error"
    NONE = "none"


class ProviderAttempt(TypedDict):
    """单个 provider 尝试结果。"""

    source: str
    status: str
    failure_type: str
    message: str

_PYTDX_BATCH_SIZE = 80
_PYTDX_HOSTS = (
    ("218.6.170.47", 7709),
    ("123.125.108.14", 7709),
    ("180.153.18.170", 7709),
    ("180.153.18.171", 7709),
    ("101.227.73.20", 7709),
    ("14.17.75.71", 7709),
)
_SSE_TURNOVER_SOURCE = "official_sse_turnover"
_SZSE_TURNOVER_SOURCE = "official_szse_turnover"
_OFFICIAL_TURNOVER_SOURCE = "official_exchange_turnover"
_PYTDX_STATS_SOURCE = "pytdx_quotes"
_AKSHARE_BREADTH_SOURCE = "akshare_spot_em"
_NEAR_COMPLETE_ABS_THRESHOLD = 50
_NEAR_COMPLETE_PCT_THRESHOLD = 0.01
_RECOVERY_MAX_ROUNDS = 2
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_NEW_YORK_TZ = ZoneInfo("America/New_York")


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

    # 市场数据分类的历史安全能力声明。
    # historical_safe=True 表示该分类支持按指定交易日获取历史数据；
    # historical_safe=False 表示该分类仅提供实时快照，不能用于历史回填。
    CATEGORY_CAPABILITIES: dict[str, dict[str, Any]] = {
        "volume": {"historical_safe": True, "description": "两市成交额（支持历史日期查询）"},
        "limit_up": {"historical_safe": True, "description": "涨停股池（zt_pool 支持历史日期）"},
        "indices": {"historical_safe": False, "description": "主要指数（仅实时快照）"},
        "statistics": {"historical_safe": False, "description": "涨跌统计（pytdx 实时报价）"},
        "sectors": {"historical_safe": False, "description": "板块涨跌（仅实时快照）"},
        "snapshot": {"historical_safe": False, "description": "全市场股票快照（仅实时）"},
    }

    @classmethod
    def get_category_capabilities(cls) -> dict[str, dict[str, Any]]:
        """返回按当前 provider 调整的分类能力。

        tickflow/mixed 模式下 TickFlow 支持历史日K，indices/sectors 升 historical_safe。
        注：实际历史回填依赖 daily_kline 历史数据，需先 `wchat ai market-data sync --days N` 预热。
        """
        import copy
        from config.settings import settings

        caps = copy.deepcopy(cls.CATEGORY_CAPABILITIES)
        if settings.market_data_provider in ("tickflow", "mixed"):
            caps["indices"]["historical_safe"] = True
            caps["sectors"]["historical_safe"] = True
        return caps

    SOURCE_STRATEGIES: dict[str, tuple[str, ...]] = {
        "indices": ("tencent_realtime", "akshare_index_spot"),
        "volume": (_OFFICIAL_TURNOVER_SOURCE, _AKSHARE_BREADTH_SOURCE),
        "statistics": (_PYTDX_STATS_SOURCE,),
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
    GLOBAL_CONTEXT_SOURCE = "yahoo_quote"
    GLOBAL_INDEX_SYMBOLS: dict[str, tuple[str, str]] = {
        "^DJI": ("DJIA", "道琼斯工业平均指数"),
        "^GSPC": ("SPX", "标普500"),
        "^IXIC": ("IXIC", "纳斯达克综合指数"),
    }
    GLOBAL_RISK_SYMBOLS: dict[str, tuple[str, str]] = {
        "^VIX": ("vix", "VIX波动率指数"),
        "DX-Y.NYB": ("dxy", "美元指数"),
        "^TNX": ("us10y", "美国10年期国债收益率"),
    }
    GLOBAL_LEADER_SYMBOLS: dict[str, str] = {
        "^SOX": "费城半导体指数",
        "NVDA": "NVIDIA",
        "MSFT": "Microsoft",
        "AAPL": "Apple",
    }
    GLOBAL_THEME_SYMBOLS: dict[str, tuple[str, str]] = {
        "^SOX": ("semiconductor", "费城半导体指数"),
        "^HXC": ("china_adr", "纳斯达克中国金龙指数"),
        "^NBI": ("biotech", "纳斯达克生物科技指数"),
        "SMH": ("semiconductor_etf", "VanEck 半导体ETF"),
        "SOXX": ("semiconductor_etf", "iShares 半导体ETF"),
        "KWEB": ("china_internet", "中概互联网ETF"),
        "FXI": ("china_large_cap", "中国大盘股ETF"),
        "XBI": ("biotech_etf", "SPDR 生物科技ETF"),
        "IBB": ("biotech_etf", "iShares 生物科技ETF"),
        "KRE": ("regional_bank", "SPDR 区域银行ETF"),
        "XLF": ("financials", "金融行业ETF"),
        "XLK": ("technology", "科技行业ETF"),
        "XLE": ("energy", "能源行业ETF"),
        "XLV": ("healthcare", "医疗保健ETF"),
        "XLY": ("consumer_discretionary", "可选消费ETF"),
        "XLP": ("consumer_staples", "必需消费ETF"),
        "XLI": ("industrials", "工业ETF"),
        "IWM": ("small_cap", "罗素2000 ETF"),
    }
    FRED_DAILY_SERIES: dict[str, str] = {
        "DJIA": "^DJI",
        "SP500": "^GSPC",
        "NASDAQCOM": "^IXIC",
        "VIXCLS": "^VIX",
        "DTWEXBGS": "DX-Y.NYB",
        "DGS10": "^TNX",
        "NASDAQ100": "QQQ",
    }
    TENCENT_GLOBAL_SYMBOLS: dict[str, str] = {
        "usDJI": "^DJI",
        "usINX": "^GSPC",
        "usIXIC": "^IXIC",
        "usSOX": "^SOX",
        "usHXC": "^HXC",
        "usNBI": "^NBI",
        "usSMH": "SMH",
        "usSOXX": "SOXX",
        "usKWEB": "KWEB",
        "usFXI": "FXI",
        "usXBI": "XBI",
        "usIBB": "IBB",
        "usKRE": "KRE",
        "usXLF": "XLF",
        "usXLK": "XLK",
        "usXLE": "XLE",
        "usXLV": "XLV",
        "usXLY": "XLY",
        "usXLP": "XLP",
        "usXLI": "XLI",
        "usIWM": "IWM",
        "usNVDA": "NVDA",
        "usMSFT": "MSFT",
        "usAAPL": "AAPL",
    }
    SINA_GLOBAL_SYMBOLS: dict[str, str] = {
        "gb_dji": "^DJI",
        "gb_inx": "^GSPC",
        "gb_ixic": "^IXIC",
        "gb_sox": "^SOX",
        "gb_hxc": "^HXC",
        "gb_nbi": "^NBI",
        "gb_smh": "SMH",
        "gb_soxx": "SOXX",
        "gb_kweb": "KWEB",
        "gb_fxi": "FXI",
        "gb_xbi": "XBI",
        "gb_ibb": "IBB",
        "gb_kre": "KRE",
        "gb_xlf": "XLF",
        "gb_xlk": "XLK",
        "gb_xle": "XLE",
        "gb_xlv": "XLV",
        "gb_xly": "XLY",
        "gb_xlp": "XLP",
        "gb_xli": "XLI",
        "gb_iwm": "IWM",
        "gb_nvda": "NVDA",
        "gb_msft": "MSFT",
        "gb_aapl": "AAPL",
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

    def _build_quality(
        self,
        *,
        status: str,
        source: str,
        actual_count: int = 0,
        expected_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "source": source,
            "actual_count": actual_count,
            "expected_count": expected_count,
        }

    def _requests_session(self, *, referer: str | None = None) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            }
        )
        if referer:
            session.headers["Referer"] = referer
        return session

    @staticmethod
    def _classify_provider_failure(error: Exception) -> tuple[str, str]:
        """将 provider 异常分类为标准化失败类型和消息。"""
        error_str = str(error)
        if "401" in error_str:
            return ProviderFailureType.UNAUTHORIZED.value, "上游拒绝访问 (401 Unauthorized)"
        if "403" in error_str:
            return ProviderFailureType.UNAUTHORIZED.value, "上游拒绝访问 (403 Forbidden)"
        if "429" in error_str:
            return ProviderFailureType.RATE_LIMITED.value, "上游限流 (429 Too Many Requests)"
        if isinstance(error, (ConnectionError, requests.ConnectionError)):
            return ProviderFailureType.NETWORK_ERROR.value, "网络连接失败"
        if "timeout" in error_str.lower() or isinstance(error, requests.Timeout):
            return ProviderFailureType.NETWORK_ERROR.value, "请求超时"
        return ProviderFailureType.NETWORK_ERROR.value, f"上游请求失败: {error_str}"

    def _empty_global_market_context(
        self,
        target_a_trade_date: date,
        *,
        status: str = "error",
        message: str = "海外市场上下文不可用",
        source: str = GLOBAL_CONTEXT_SOURCE,
    ) -> dict[str, Any]:
        captured_at = datetime.now(_SHANGHAI_TZ).isoformat()
        session = self._detect_us_market_session()
        return {
            "status": status,
            "target_a_trade_date": target_a_trade_date.isoformat(),
            "captured_at": captured_at,
            "as_of": None,
            "session": session,
            "source": source,
            "message": message,
            "source_attempts": [],
            "degraded": False,
            "us_market": {
                "status": status,
                "session": session,
                "as_of": None,
                "indices": [],
                "risk_signals": {},
                "leaders": [],
                "theme_indices": [],
                "source": source,
                "message": message,
            },
        }

    def _detect_us_market_session(self, now: datetime | None = None) -> str:
        """根据纽约当地时间粗略判断美股交易阶段。"""
        ny_now = (now or datetime.now(_NEW_YORK_TZ)).astimezone(_NEW_YORK_TZ)
        if ny_now.weekday() >= 5:
            return "closed"

        current = ny_now.time()
        if time_type(4, 0) <= current < time_type(9, 30):
            return "pre_market"
        if time_type(9, 30) <= current < time_type(16, 0):
            return "regular"
        if time_type(16, 0) <= current < time_type(20, 0):
            return "post_market"
        return "closed"

    def _quote_as_of(self, quote: Mapping[str, Any]) -> str | None:
        timestamp = self._first_present(
            quote.get("regularMarketTime"),
            quote.get("postMarketTime"),
            quote.get("preMarketTime"),
        )
        try:
            if timestamp:
                return datetime.fromtimestamp(int(timestamp), tz=_SHANGHAI_TZ).isoformat()
        except (TypeError, ValueError, OSError):
            return None
        return None

    def _first_present(self, *values: Any) -> Any:
        for value in values:
            if value is not None and value != "":
                return value
        return None

    def _quote_price(self, quote: Mapping[str, Any]) -> float | None:
        return self._to_float(
            self._first_present(
                quote.get("regularMarketPrice"),
                quote.get("postMarketPrice"),
                quote.get("preMarketPrice"),
            )
        )

    def _quote_change_pct(self, quote: Mapping[str, Any]) -> float | None:
        value = self._to_float(
            self._first_present(
                quote.get("regularMarketChangePercent"),
                quote.get("postMarketChangePercent"),
                quote.get("preMarketChangePercent"),
            )
        )
        if value is not None:
            return round(value / 100, 6)

        price = self._quote_price(quote)
        previous_close = self._to_float(
            self._first_present(
                quote.get("regularMarketPreviousClose"),
                quote.get("chartPreviousClose"),
                quote.get("previousClose"),
            )
        )
        if price is None or previous_close in (None, 0):
            return None
        return round((price - previous_close) / previous_close, 6)

    def _normalize_global_quote_rows(
        self,
        rows: list[Mapping[str, Any]],
        target_a_trade_date: date,
    ) -> dict[str, Any]:
        by_symbol = {str(row.get("symbol", "")): row for row in rows}
        as_of_values = [self._quote_as_of(row) for row in rows]
        as_of = max([value for value in as_of_values if value], default=None)
        session = self._detect_us_market_session()

        indices: list[dict[str, Any]] = []
        missing: list[str] = []
        for yahoo_symbol, (symbol, name) in self.GLOBAL_INDEX_SYMBOLS.items():
            row = by_symbol.get(yahoo_symbol)
            if not row:
                missing.append(symbol)
                continue
            price = self._quote_price(row)
            change_pct = self._quote_change_pct(row)
            if price is None or change_pct is None:
                missing.append(symbol)
                continue
            indices.append({
                "symbol": symbol,
                "name": name,
                "price": price,
                "change_pct": change_pct,
            })

        risk_signals: dict[str, dict[str, Any]] = {}
        for yahoo_symbol, (key, name) in self.GLOBAL_RISK_SYMBOLS.items():
            row = by_symbol.get(yahoo_symbol)
            if not row:
                missing.append(key)
                continue
            value = self._quote_price(row)
            change_pct = self._quote_change_pct(row)
            if value is None:
                missing.append(key)
                continue
            signal = {"name": name, "value": value}
            if key == "us10y":
                change = self._to_float(row.get("regularMarketChange"))
                if change is not None:
                    signal["change_bp"] = round(change * 10, 2)
            elif change_pct is not None:
                signal["change_pct"] = change_pct
            risk_signals[key] = signal

        leaders: list[dict[str, Any]] = []
        for yahoo_symbol, name in self.GLOBAL_LEADER_SYMBOLS.items():
            row = by_symbol.get(yahoo_symbol)
            if not row:
                continue
            change_pct = self._quote_change_pct(row)
            if change_pct is None:
                continue
            leaders.append({
                "symbol": str(row.get("symbol", yahoo_symbol)).lstrip("^"),
                "name": name,
                "change_pct": change_pct,
            })

        theme_indices: list[dict[str, Any]] = []
        for yahoo_symbol, (theme_key, name) in self.GLOBAL_THEME_SYMBOLS.items():
            row = by_symbol.get(yahoo_symbol)
            if not row:
                continue
            price = self._quote_price(row)
            change_pct = self._quote_change_pct(row)
            if price is None or change_pct is None:
                continue
            theme_indices.append({
                "symbol": str(row.get("symbol", yahoo_symbol)).lstrip("^"),
                "theme": theme_key,
                "name": name,
                "price": price,
                "change_pct": change_pct,
            })

        status = "ok"
        if not indices and not risk_signals and not leaders:
            status = "error"
        elif len(indices) < len(self.GLOBAL_INDEX_SYMBOLS) or len(risk_signals) < len(self.GLOBAL_RISK_SYMBOLS):
            status = "partial"

        message = "海外市场上下文获取完成"
        if status == "partial":
            message = f"海外市场上下文部分可用，缺失: {', '.join(missing)}" if missing else "海外市场上下文部分可用"
        elif status == "error":
            message = "海外市场上下文不可用"

        captured_at = datetime.now(_SHANGHAI_TZ).isoformat()
        return {
            "status": status,
            "target_a_trade_date": target_a_trade_date.isoformat(),
            "captured_at": captured_at,
            "as_of": as_of,
            "session": session,
            "source": self.GLOBAL_CONTEXT_SOURCE,
            "message": message,
            "us_market": {
                "status": status,
                "session": session,
                "as_of": as_of,
                "indices": indices,
                "risk_signals": risk_signals,
                "leaders": leaders[:5],
                "theme_indices": theme_indices[:12],
                "source": self.GLOBAL_CONTEXT_SOURCE,
                "message": message,
            },
        }

    def _fetch_yahoo_quotes_sync(self, symbols: list[str]) -> list[Mapping[str, Any]]:
        session = self._requests_session(referer="https://finance.yahoo.com/")
        try:
            response = session.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": ",".join(symbols)},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("quoteResponse", {}).get("result", [])
            if not isinstance(result, list):
                raise ValueError("invalid yahoo quote result")
            return [row for row in result if isinstance(row, Mapping)]
        finally:
            session.close()

    def _parse_datetime_timestamp(self, value: str, tz: ZoneInfo) -> int | None:
        try:
            parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
            return int(parsed.timestamp())
        except (TypeError, ValueError):
            return None

    def _fetch_tencent_global_quotes_sync(self) -> list[Mapping[str, Any]]:
        """从腾讯行情接口获取当天海外核心指数和美股龙头实时数据。"""
        session = self._requests_session(referer="https://stockapp.finance.qq.com/")
        try:
            response = session.get(
                "https://web.sqt.gtimg.cn/q=" + ",".join(self.TENCENT_GLOBAL_SYMBOLS),
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = response.content.decode("gbk", errors="ignore")

            rows: list[Mapping[str, Any]] = []
            for match in re.finditer(r'v_(\w+)="([^"]*)"', text):
                code = match.group(1)
                symbol = self.TENCENT_GLOBAL_SYMBOLS.get(code)
                if not symbol:
                    continue
                data = match.group(2).split("~")
                if len(data) < 33 or data[0] != "200":
                    continue
                price = self._to_float(data[3])
                previous_close = self._to_float(data[4])
                change_pct = self._to_float(data[32])
                timestamp = self._parse_datetime_timestamp(data[30], _NEW_YORK_TZ)
                if price is None or change_pct is None:
                    continue
                rows.append({
                    "symbol": symbol,
                    "regularMarketPrice": price,
                    "regularMarketPreviousClose": previous_close,
                    "regularMarketChangePercent": change_pct,
                    "regularMarketChange": self._to_float(data[31]),
                    "regularMarketTime": timestamp,
                })
            return rows
        finally:
            session.close()

    def _fetch_sina_global_quotes_sync(self) -> list[Mapping[str, Any]]:
        """从新浪行情接口获取当天海外核心指数和美股龙头实时数据。"""
        session = self._requests_session(referer="https://finance.sina.com.cn/")
        try:
            response = session.get(
                "https://hq.sinajs.cn/list=" + ",".join(self.SINA_GLOBAL_SYMBOLS),
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = response.content.decode("gb18030", errors="ignore")

            rows: list[Mapping[str, Any]] = []
            for match in re.finditer(r'var hq_str_(\w+)="([^"]*)"', text):
                code = match.group(1)
                symbol = self.SINA_GLOBAL_SYMBOLS.get(code)
                if not symbol:
                    continue
                data = match.group(2).split(",")
                if len(data) < 5 or not data[1]:
                    continue
                price = self._to_float(data[1])
                change_pct = self._to_float(data[2])
                timestamp = self._parse_datetime_timestamp(data[3], _SHANGHAI_TZ)
                previous_close = self._to_float(data[26]) if len(data) > 26 else None
                if price is None or change_pct is None:
                    continue
                rows.append({
                    "symbol": symbol,
                    "regularMarketPrice": price,
                    "regularMarketPreviousClose": previous_close,
                    "regularMarketChangePercent": change_pct,
                    "regularMarketChange": self._to_float(data[4]),
                    "regularMarketTime": timestamp,
                })
            return rows
        finally:
            session.close()

    def _fetch_yahoo_chart_sync(self, symbols: list[str]) -> list[Mapping[str, Any]]:
        """使用 Yahoo chart API 获取行情数据（作为 v7 quote 的 fallback provider）。"""
        session = self._requests_session(referer="https://finance.yahoo.com/")
        try:
            results: list[Mapping[str, Any]] = []
            errors: list[Exception] = []
            for symbol in symbols:
                try:
                    response = session.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                        params={"range": "1d", "interval": "1d"},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    chart_result = payload.get("chart", {}).get("result", [{}])
                    if not chart_result:
                        continue
                    meta = chart_result[0].get("meta", {})
                    if not meta.get("regularMarketPrice"):
                        continue
                    results.append({
                        "symbol": symbol,
                        "regularMarketPrice": meta.get("regularMarketPrice"),
                        "regularMarketPreviousClose": meta.get("regularMarketPreviousClose"),
                        "chartPreviousClose": meta.get("chartPreviousClose"),
                        "previousClose": meta.get("previousClose"),
                        "regularMarketChangePercent": meta.get("regularMarketChangePercent"),
                        "regularMarketChange": meta.get("regularMarketChange"),
                        "regularMarketTime": meta.get("regularMarketTime"),
                        "postMarketPrice": meta.get("postMarketPrice"),
                        "postMarketChangePercent": meta.get("postMarketChangePercent"),
                        "postMarketTime": meta.get("postMarketTime"),
                        "preMarketPrice": meta.get("preMarketPrice"),
                        "preMarketChangePercent": meta.get("preMarketChangePercent"),
                        "preMarketTime": meta.get("preMarketTime"),
                    })
                except Exception as e:
                    errors.append(e)
                    continue
            if not results and errors:
                raise errors[-1]
            return results
        finally:
            session.close()

    def _fetch_fred_daily_sync(self) -> list[Mapping[str, Any]]:
        """使用 FRED 公开日频 CSV 作为 Yahoo 全链路失败后的 fallback。"""
        session = self._requests_session()
        try:
            results: list[Mapping[str, Any]] = []
            for series_id, symbol in self.FRED_DAILY_SERIES.items():
                response = session.get(
                    "https://fred.stlouisfed.org/graph/fredgraph.csv",
                    params={"id": series_id},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                values: list[tuple[date, float]] = []
                for row in csv.DictReader(response.text.splitlines()):
                    raw_date = row.get("observation_date")
                    raw_value = row.get(series_id)
                    if not raw_date or raw_value in (None, "", "."):
                        continue
                    try:
                        values.append((date.fromisoformat(raw_date), float(raw_value)))
                    except (TypeError, ValueError):
                        continue

                if len(values) < 2:
                    continue

                current_date, current_value = values[-1]
                _, previous_value = values[-2]
                if previous_value == 0:
                    continue

                change = current_value - previous_value
                market_time = datetime.combine(
                    current_date,
                    time_type(16, 0),
                    tzinfo=_NEW_YORK_TZ,
                )
                regular_market_change = change * 10 if symbol == "^TNX" else change
                results.append({
                    "symbol": symbol,
                    "regularMarketPrice": current_value,
                    "regularMarketPreviousClose": previous_value,
                    "regularMarketChangePercent": change / previous_value * 100,
                    "regularMarketChange": regular_market_change,
                    "regularMarketTime": int(market_time.timestamp()),
                })
            return results
        finally:
            session.close()

    async def get_global_market_context(self, target_a_trade_date: date) -> dict[str, Any]:
        """获取与 A 股目标交易日关联的海外市场上下文。

        使用有序 provider chain: tencent_realtime -> sina_realtime -> yahoo_quote -> yahoo_chart -> fred_daily，
        短路于首个可用结果，并记录 source_attempts 和 degraded 元数据。
        """
        if _DISABLE_NETWORK:
            return self._empty_global_market_context(
                target_a_trade_date,
                status="error",
                message="网络请求已禁用",
                source="disabled",
            )

        symbols = (
            list(self.GLOBAL_INDEX_SYMBOLS)
            + list(self.GLOBAL_RISK_SYMBOLS)
            + list(self.GLOBAL_LEADER_SYMBOLS)
        )

        source_attempts: list[ProviderAttempt] = []

        # Provider 1: Tencent realtime quote (primary, no API key)
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, self._fetch_tencent_global_quotes_sync)
            if rows:
                result = self._normalize_global_quote_rows(rows, target_a_trade_date)
                result["source"] = "tencent_realtime"
                result["us_market"]["source"] = "tencent_realtime"
                source_attempts.append(ProviderAttempt(
                    source="tencent_realtime",
                    status=result["status"],
                    failure_type=ProviderFailureType.NONE.value,
                    message="腾讯实时源获取成功",
                ))
                result["source_attempts"] = source_attempts
                result["degraded"] = False
                return result
            source_attempts.append(ProviderAttempt(
                source="tencent_realtime",
                status="error",
                failure_type=ProviderFailureType.EMPTY.value,
                message="腾讯实时源返回空数据",
            ))
        except Exception as e:
            failure_type, message = self._classify_provider_failure(e)
            source_attempts.append(ProviderAttempt(
                source="tencent_realtime",
                status="error",
                failure_type=failure_type,
                message=message,
            ))
            logger.debug("海外市场腾讯实时源获取失败: %s", message)

        # Provider 2: Sina realtime quote (fallback, no API key)
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, self._fetch_sina_global_quotes_sync)
            if rows:
                result = self._normalize_global_quote_rows(rows, target_a_trade_date)
                result["source"] = "sina_realtime"
                result["us_market"]["source"] = "sina_realtime"
                source_attempts.append(ProviderAttempt(
                    source="sina_realtime",
                    status=result["status"],
                    failure_type=ProviderFailureType.NONE.value,
                    message="新浪实时源获取成功",
                ))
                result["source_attempts"] = source_attempts
                result["degraded"] = True
                logger.info("海外市场上下文 fallback 成功 (sina_realtime)")
                return result
            source_attempts.append(ProviderAttempt(
                source="sina_realtime",
                status="error",
                failure_type=ProviderFailureType.EMPTY.value,
                message="新浪实时源返回空数据",
            ))
        except Exception as e:
            failure_type, message = self._classify_provider_failure(e)
            source_attempts.append(ProviderAttempt(
                source="sina_realtime",
                status="error",
                failure_type=failure_type,
                message=message,
            ))
            logger.debug("海外市场新浪实时源获取失败: %s", message)

        # Provider 3: Yahoo v7 quote
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, lambda: self._fetch_yahoo_quotes_sync(symbols))
            if rows:
                result = self._normalize_global_quote_rows(rows, target_a_trade_date)
                source_attempts.append(ProviderAttempt(
                    source="yahoo_quote",
                    status=result["status"],
                    failure_type=ProviderFailureType.NONE.value,
                    message="Yahoo quote 获取成功",
                ))
                result["source_attempts"] = source_attempts
                result["degraded"] = True
                logger.info("海外市场上下文 fallback 成功 (yahoo_quote)")
                return result
            source_attempts.append(ProviderAttempt(
                source="yahoo_quote",
                status="error",
                failure_type=ProviderFailureType.EMPTY.value,
                message="海外市场上游返回空数据",
            ))
        except Exception as e:
            failure_type, message = self._classify_provider_failure(e)
            source_attempts.append(ProviderAttempt(
                source="yahoo_quote",
                status="error",
                failure_type=failure_type,
                message=message,
            ))
            logger.debug("海外市场主源获取失败: %s", message)

        # Provider 4: Yahoo v8 chart (fallback)
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, lambda: self._fetch_yahoo_chart_sync(symbols))
            if rows:
                result = self._normalize_global_quote_rows(rows, target_a_trade_date)
                result["source"] = "yahoo_chart"
                result["us_market"]["source"] = "yahoo_chart"
                source_attempts.append(ProviderAttempt(
                    source="yahoo_chart",
                    status=result["status"],
                    failure_type=ProviderFailureType.NONE.value,
                    message="fallback 获取成功",
                ))
                result["source_attempts"] = source_attempts
                result["degraded"] = True
                logger.info("海外市场上下文 fallback 成功 (yahoo_chart)")
                return result
            source_attempts.append(ProviderAttempt(
                source="yahoo_chart",
                status="error",
                failure_type=ProviderFailureType.EMPTY.value,
                message="海外市场 fallback 返回空数据",
            ))
        except Exception as e:
            failure_type, message = self._classify_provider_failure(e)
            source_attempts.append(ProviderAttempt(
                source="yahoo_chart",
                status="error",
                failure_type=failure_type,
                message=message,
            ))
            logger.debug("海外市场 fallback 获取失败: %s", message)

        # Provider 5: FRED daily close data (low-frequency fallback)
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, self._fetch_fred_daily_sync)
            if rows:
                result = self._normalize_global_quote_rows(rows, target_a_trade_date)
                result["source"] = "fred_daily"
                result["us_market"]["source"] = "fred_daily"
                source_attempts.append(ProviderAttempt(
                    source="fred_daily",
                    status=result["status"],
                    failure_type=ProviderFailureType.NONE.value,
                    message="日频 fallback 获取成功",
                ))
                result["source_attempts"] = source_attempts
                result["degraded"] = True
                logger.info("海外市场上下文 fallback 成功 (fred_daily)")
                return result
            source_attempts.append(ProviderAttempt(
                source="fred_daily",
                status="error",
                failure_type=ProviderFailureType.EMPTY.value,
                message="海外市场日频 fallback 返回空数据",
            ))
        except Exception as e:
            failure_type, message = self._classify_provider_failure(e)
            source_attempts.append(ProviderAttempt(
                source="fred_daily",
                status="error",
                failure_type=failure_type,
                message=message,
            ))
            logger.debug("海外市场日频 fallback 获取失败: %s", message)

        # 所有 provider 均失败 — 输出一次聚合 warning
        failure_summary = ", ".join(
            f"{a['source']}={a['failure_type']}" for a in source_attempts if a["failure_type"] != "none"
        )
        logger.warning(
            "海外市场上下文所有数据源失败: %s",
            failure_summary or "unknown",
        )
        last_attempt = source_attempts[-1] if source_attempts else None
        result = self._empty_global_market_context(
            target_a_trade_date,
            status="error",
            message=last_attempt["message"] if last_attempt else "所有海外市场上游均失败",
            source=last_attempt["source"] if last_attempt else "none",
        )
        result["source_attempts"] = source_attempts
        result["degraded"] = False
        return result

    def _parse_jsonp_payload(self, payload: str) -> Any:
        text = payload.strip()
        if not text:
            raise ValueError("empty payload")
        match = re.fullmatch(r"[^(]+\((.*)\)", text, re.S)
        if not match:
            raise ValueError("invalid jsonp payload")
        return json.loads(match.group(1))

    def _parse_numeric_text(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        text = str(value).replace(",", "").strip()
        return self._to_float(text)

    def _extract_sse_stock_turnover(self, payload: dict[str, Any]) -> tuple[float, str]:
        rows = payload.get("result") or []
        if not isinstance(rows, list):
            raise ValueError("invalid SSE response rows")
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("PRODUCT_CODE", "")) == "17":
                turnover = self._parse_numeric_text(row.get("TRADE_AMT"))
                trade_date = str(row.get("TRADE_DATE", "")).strip()
                if turnover is None or not trade_date:
                    break
                return turnover, trade_date
        raise ValueError("SSE turnover row not found")

    def _extract_szse_stock_turnover(self, payload: Any) -> tuple[float, str]:
        if not isinstance(payload, list) or not payload:
            raise ValueError("invalid SZSE payload")
        first = payload[0] if isinstance(payload[0], Mapping) else {}
        metadata = first.get("metadata") if isinstance(first, Mapping) else {}
        rows = first.get("data") if isinstance(first, Mapping) else None
        if not isinstance(rows, list):
            raise ValueError("invalid SZSE response rows")
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if "成交金额" in str(row.get("zbmc", "")):
                turnover = self._parse_numeric_text(row.get("gp"))
                if turnover is None:
                    break
                trade_date = ""
                conditions = metadata.get("conditions") if isinstance(metadata, Mapping) else None
                if isinstance(conditions, list):
                    for item in conditions:
                        if isinstance(item, Mapping) and item.get("name") == "txtQueryDate":
                            trade_date = str(item.get("defaultValue", "")).replace("-", "")
                            break
                return turnover, trade_date
        raise ValueError("SZSE turnover row not found")

    def _fetch_sse_official_turnover_sync(self, trade_date: date) -> tuple[float, str]:
        session = self._requests_session(referer="https://www.sse.com.cn/market/stockdata/overview/day/")
        try:
            response = session.get(
                "https://query.sse.com.cn/commonQuery.do",
                params={
                    "jsonCallBack": "jsonpCallback",
                    "sqlId": "COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C",
                    "PRODUCT_CODE": "01,02,03,11,17",
                    "type": "inParams",
                    "SEARCH_DATE": trade_date.isoformat(),
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = self._parse_jsonp_payload(response.text)
            return self._extract_sse_stock_turnover(payload)
        finally:
            session.close()

    def _fetch_szse_official_turnover_sync(self, trade_date: date) -> tuple[float, str]:
        session = self._requests_session(referer="https://www.szse.cn/www/market/stock/situation/daily/index.html")
        try:
            response = session.get(
                "https://www.szse.cn/api/report/ShowReport/data",
                params={
                    "SHOWTYPE": "JSON",
                    "CATALOGID": "scsj_gprdgk_after",
                    "txtQueryDate": trade_date.isoformat(),
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return self._extract_szse_stock_turnover(payload)
        finally:
            session.close()

    async def _fetch_sse_official_turnover(self, trade_date: date) -> tuple[float, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._fetch_sse_official_turnover_sync(trade_date))

    async def _fetch_szse_official_turnover(self, trade_date: date) -> tuple[float, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._fetch_szse_official_turnover_sync(trade_date))

    def _is_pytdx_a_share(self, market: int, code: str) -> bool:
        if market == 0:
            return code.startswith(("00", "30"))
        if market == 1:
            return code.startswith(("60", "68"))
        return False

    def _build_pytdx_a_share_universe(self, api: Any) -> list[tuple[int, str]]:
        universe: list[tuple[int, str]] = []
        for market in (0, 1):
            total = int(api.get_security_count(market) or 0)
            for start in range(0, total, 1000):
                rows = api.get_security_list(market, start)
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, Mapping):
                        continue
                    code = str(row.get("code", "")).strip()
                    if self._is_pytdx_a_share(market, code):
                        universe.append((market, code))
        return universe

    def _compute_statistics_from_pytdx_quotes(self, rows: list[dict[str, Any]]) -> tuple[dict[str, int], int]:
        up_count = 0
        down_count = 0
        flat_count = 0
        actual_count = 0

        for item in rows:
            if not isinstance(item, Mapping):
                continue
            price = self._to_float(item.get("price"))
            last_close = self._to_float(item.get("last_close"))
            if price is None or last_close in (None, 0):
                continue
            actual_count += 1
            if price > last_close:
                up_count += 1
            elif price < last_close:
                down_count += 1
            else:
                flat_count += 1

        return {
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
        }, actual_count

    def _recover_pytdx_missing(
        self,
        api: Any,
        missing_universe: list[tuple[int, str]],
    ) -> list[dict[str, Any]]:
        """对缺失证券执行有限轮次的定向补抓。"""
        recovered: list[dict[str, Any]] = []
        remaining = list(missing_universe)

        for round_num in range(1, _RECOVERY_MAX_ROUNDS + 1):
            if not remaining:
                break
            round_quotes: list[dict[str, Any]] = []
            for start in range(0, len(remaining), _PYTDX_BATCH_SIZE):
                batch = remaining[start:start + _PYTDX_BATCH_SIZE]
                try:
                    quotes = api.get_security_quotes(batch)
                    if isinstance(quotes, list):
                        round_quotes.extend(quotes)
                except Exception as e:
                    logger.warning("pytdx 补抓第 %d 轮失败: %s", round_num, e)

            if not round_quotes:
                break

            recovered.extend(round_quotes)
            recovered_codes = {
                str(item.get("code", ""))
                for item in round_quotes
                if isinstance(item, Mapping)
            }
            prev_remaining = len(remaining)
            remaining = [(m, c) for m, c in remaining if c not in recovered_codes]
            logger.info(
                "pytdx 补抓第 %d 轮: 恢复 %d, 仍缺失 %d",
                round_num, prev_remaining - len(remaining), len(remaining),
            )

        if recovered:
            logger.info("pytdx 补抓完成: 共恢复 %d 条", len(recovered))
        return recovered

    @staticmethod
    def _determine_statistics_quality(actual_count: int, expected_count: int) -> str:
        """判定涨跌统计质量状态（四态模型: ok / near-complete / partial / error）。"""
        if expected_count == 0:
            return "error"
        if actual_count >= expected_count:
            return "ok"
        if actual_count == 0:
            return "error"
        gap = expected_count - actual_count
        threshold = max(
            _NEAR_COMPLETE_ABS_THRESHOLD,
            int(expected_count * _NEAR_COMPLETE_PCT_THRESHOLD),
        )
        return "near-complete" if gap <= threshold else "partial"

    def _fetch_pytdx_statistics_sync(self) -> tuple[dict[str, int], dict[str, Any]]:
        error_quality = self._build_quality(status="error", source=_PYTDX_STATS_SOURCE)
        try:
            from pytdx.hq import TdxHq_API
        except ImportError:
            logger.info("pytdx 未安装，跳过涨跌统计主源")
            return {"up_count": 0, "down_count": 0, "flat_count": 0}, error_quality

        expected_count = 0
        attempt_errors: list[str] = []
        for host, port in _PYTDX_HOSTS:
            api = TdxHq_API(heartbeat=False, multithread=False)
            try:
                with api.connect(host, port, time_out=min(self.timeout, 5)):
                    universe = self._build_pytdx_a_share_universe(api)
                    expected_count = len(universe)
                    if expected_count == 0:
                        break

                    quotes_rows: list[dict[str, Any]] = []
                    for start in range(0, expected_count, _PYTDX_BATCH_SIZE):
                        batch = universe[start:start + _PYTDX_BATCH_SIZE]
                        quotes = api.get_security_quotes(batch)
                        if isinstance(quotes, list):
                            quotes_rows.extend(quotes)

                    # 识别首轮缺失并定向补抓
                    fetched_codes = {
                        str(item.get("code", ""))
                        for item in quotes_rows
                        if isinstance(item, Mapping)
                    }
                    missing_universe = [
                        (m, c) for m, c in universe if c not in fetched_codes
                    ]
                    if missing_universe:
                        logger.info(
                            "pytdx 首轮缺失 %d/%d, 开始补抓",
                            len(missing_universe), expected_count,
                        )
                        quotes_rows.extend(
                            self._recover_pytdx_missing(api, missing_universe)
                        )

                    statistics, actual_count = self._compute_statistics_from_pytdx_quotes(quotes_rows)
                    status = self._determine_statistics_quality(actual_count, expected_count)
                    return statistics, self._build_quality(
                        status=status,
                        source=_PYTDX_STATS_SOURCE,
                        actual_count=actual_count,
                        expected_count=expected_count,
                    )
            except Exception as e:
                err_msg = f"{host}:{port} - {e}"
                attempt_errors.append(err_msg)
                logger.debug("pytdx 主站尝试失败: %s", err_msg)

        last_error = attempt_errors[-1] if attempt_errors else "unknown"
        logger.warning(
            "pytdx 涨跌统计全部主站失败: attempts=%d, last_error=%s",
            len(attempt_errors), last_error,
        )
        fallback_quality = self._build_quality(
            status="error" if expected_count == 0 else "partial",
            source=_PYTDX_STATS_SOURCE,
            actual_count=0,
            expected_count=expected_count,
        )
        return {"up_count": 0, "down_count": 0, "flat_count": 0}, fallback_quality

    async def _fetch_pytdx_statistics(self) -> tuple[dict[str, int], dict[str, Any]]:
        if _DISABLE_NETWORK:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}, self._build_quality(
                status="error",
                source="disabled",
            )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_pytdx_statistics_sync)

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

    def _normalize_sector_rows(self, rows: list[dict[str, Any]], top_n: int = 10) -> dict[str, list]:
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

    def _normalize_limit_up_rows(self, rows: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
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
        return normalized[:limit] if limit is not None else normalized

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

    async def _get_sector_data_from_stock_sector_spot(self, top_n: int = 10) -> dict[str, list]:
        df = await self._retry_request(ak.stock_sector_spot, indicator="概念")
        rows = self._records_from_dataframe(df)
        return self._normalize_sector_rows(rows, top_n=top_n)

    async def _get_sector_data_from_board_name_em(self, top_n: int = 10) -> dict[str, list]:
        df = await self._retry_request(ak.stock_board_concept_name_em)
        rows = self._records_from_dataframe(df)
        return self._normalize_sector_rows(rows, top_n=top_n)

    async def _get_sector_data_from_eastmoney(self, top_n: int = 10) -> dict[str, list]:
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
            for _, row in df[df["涨跌幅"] >= 9.9].iterrows()
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

    async def _get_volume_with_quality(
        self,
        trade_date: date | None = None,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        """获取成交额及其质量状态。"""
        if _DISABLE_NETWORK:
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}, self._build_quality(
                status="error",
                source="disabled",
            )

        if trade_date is None:
            trade_date = date.today()

        sse_turnover = None
        szse_turnover = None
        success_count = 0

        try:
            sse_turnover, _ = await self._fetch_sse_official_turnover(trade_date)
            success_count += 1
        except Exception as e:
            logger.warning("上交所官方成交额获取失败: %s", e)

        try:
            szse_turnover, _ = await self._fetch_szse_official_turnover(trade_date)
            success_count += 1
        except Exception as e:
            logger.warning("深交所官方成交额获取失败: %s", e)

        if success_count == 2 and sse_turnover is not None and szse_turnover is not None:
            return {
                "sh_volume": round(sse_turnover, 2),
                "sz_volume": round(szse_turnover, 2),
                "total_volume": round(sse_turnover + szse_turnover, 2),
            }, self._build_quality(
                status="ok",
                source=_OFFICIAL_TURNOVER_SOURCE,
                actual_count=2,
                expected_count=2,
            )

        try:
            fallback = await self._get_volume_data_from_spot_em()
            if fallback.get("total_volume", 0) > 0:
                return fallback, self._build_quality(
                    status="ok",
                    source=_AKSHARE_BREADTH_SOURCE,
                    actual_count=success_count,
                    expected_count=2,
                )
        except Exception as e:
            logger.warning("成交额旧链路兜底失败: %s", e)

        status = "partial" if success_count > 0 else "error"
        return {
            "sh_volume": 0,
            "sz_volume": 0,
            "total_volume": 0,
        }, self._build_quality(
            status=status,
            source=_OFFICIAL_TURNOVER_SOURCE,
            actual_count=success_count,
            expected_count=2,
        )

    async def _get_statistics_with_quality(self) -> tuple[dict[str, int], dict[str, Any]]:
        """获取涨跌统计及其质量状态。"""
        if _DISABLE_NETWORK:
            return {"up_count": 0, "down_count": 0, "flat_count": 0}, self._build_quality(
                status="error",
                source="disabled",
            )

        statistics, quality = await self._fetch_pytdx_statistics()
        if quality["status"] in ("ok", "near-complete"):
            return statistics, quality

        if quality.get("status") == "partial" and quality.get("actual_count", 0) > 0:
            return statistics, quality

        return {"up_count": 0, "down_count": 0, "flat_count": 0}, quality

    async def get_volume_data(
        self,
        stocks: list[dict] | None = None,
        trade_date: date | None = None,
    ) -> dict[str, float]:
        """获取两市成交额数据。"""
        if stocks is not None:
            return self.compute_volume_data(stocks)
        try:
            volume, _ = await self._get_volume_with_quality(trade_date=trade_date)
            return volume
        except Exception as e:
            logger.warning("获取成交额失败: %s", e)
            return {"sh_volume": 0, "sz_volume": 0, "total_volume": 0}

    async def get_statistics(self, stocks: list[dict] | None = None) -> dict[str, int]:
        """获取涨跌统计数据。"""
        if stocks is not None:
            return self.compute_statistics(stocks)
        try:
            statistics, _ = await self._get_statistics_with_quality()
            return statistics
        except Exception as e:
            logger.warning("获取涨跌统计失败: %s", e)
            return {"up_count": 0, "down_count": 0, "flat_count": 0}

    async def get_sector_data(self, top_n: int = 10) -> dict[str, list]:
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
        stocks, _ = await self._get_limit_up_with_quality(trade_date=trade_date)
        return stocks

    async def _get_limit_up_with_quality(
        self,
        trade_date: Optional[date | datetime] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """获取涨停股及其来源质量标记。"""
        if _DISABLE_NETWORK:
            return [], {"source_type": "none", "status": "error"}

        # 优先专用涨停池
        try:
            result = await self._get_limit_up_from_zt_pool(trade_date=trade_date)
            if result is not None:
                return result, {"source_type": "dedicated_pool", "status": "ok"}
        except Exception as e:
            logger.warning("涨停池主源失败: %s", e)

        # 快照兜底
        try:
            result = await self._get_limit_up_from_snapshot()
            if result is not None:
                return result, {"source_type": "approximate_candidates", "status": "ok"}
        except Exception as e:
            logger.warning("涨停股快照兜底失败: %s", e)

        # akshare spot 兜底
        try:
            result = await self._get_limit_up_from_spot_em()
            if result is not None:
                return result, {"source_type": "approximate_candidates", "status": "ok"}
        except Exception as e:
            logger.warning("涨停股 spot 兜底失败: %s", e)

        return [], {"source_type": "none", "status": "error"}

    async def get_all_market_data(self, trade_date: Optional[date | datetime] = None) -> dict[str, Any]:
        """获取所有市场数据。

        成交额和涨跌统计允许来自不同主源，但必须共享同一交易日语义。
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

        # TickFlow 数据源分流（task 7.2）：tickflow/mixed 时优先走 TickFlowProvider
        from config.settings import settings as _settings

        if _settings.market_data_provider in ("tickflow", "mixed"):
            tf_data = await self._get_market_data_from_tickflow(trade_date)
            if tf_data is not None:
                return tf_data
            if _settings.market_data_provider == "tickflow":
                logger.warning("TickFlow 模式取数失败，返回空数据")
                return {
                    "indices": {},
                    "volume": {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
                    "statistics": {"up_count": 0, "down_count": 0, "flat_count": 0},
                    "sectors": {"top_sectors": [], "bottom_sectors": []},
                    "limit_up": [],
                    "fetch_time": datetime.now().isoformat(),
                    "breadth_quality": {
                        "volume": {"status": "error", "source": "tickflow"},
                        "statistics": {"status": "error", "source": "tickflow"},
                    },
                }
            # mixed: TickFlow 不全，落到下方原逻辑

        logger.info("开始获取市场数据...")

        if isinstance(trade_date, datetime):
            trade_date = trade_date.date()

        (volume_result, statistics_result, other_results) = await asyncio.gather(
            self._get_volume_with_quality(trade_date=trade_date),
            self._get_statistics_with_quality(),
            asyncio.gather(
                self.get_index_data(),
                self.get_sector_data(),
                self._get_limit_up_with_quality(trade_date=trade_date),
                return_exceptions=True,
            ),
        )
        volume, volume_quality = volume_result
        statistics, statistics_quality = statistics_result

        limit_up_raw = other_results[2]
        if isinstance(limit_up_raw, Exception):
            limit_up: list[dict[str, Any]] = []
            limit_up_quality: dict[str, Any] = {"source_type": "none", "status": "error"}
        else:
            limit_up, limit_up_quality = limit_up_raw

        market_data = {
            "indices": other_results[0] if not isinstance(other_results[0], Exception) else {},
            "volume": volume,
            "statistics": statistics,
            "sectors": other_results[1] if not isinstance(other_results[1], Exception) else {},
            "limit_up": limit_up,
            "fetch_time": datetime.now().isoformat(),
            "breadth_quality": {
                "volume": volume_quality,
                "statistics": statistics_quality,
            },
            "limit_up_quality": limit_up_quality,
        }

        logger.info("市场数据获取完成")
        return market_data

    async def _get_market_data_from_tickflow(
        self, trade_date: Optional[date | datetime] = None
    ) -> Optional[dict[str, Any]]:
        """从 TickFlowProvider 组装 market_data dict（小数口径，绕过 _normalize_pct）。

        核心（volume/statistics）不可用时返回 None，供 mixed 模式 fallback 原逻辑。
        """
        from src.api.market_providers.tickflow.provider import TickFlowProvider
        from src.storage.database import get_db

        db = await get_db()
        provider = TickFlowProvider(db)
        try:
            indices, volume, statistics, sectors, limit_up = await asyncio.gather(
                provider.get_indices(trade_date),
                provider.get_volume(trade_date),
                provider.get_statistics(trade_date),
                provider.get_sectors(trade_date),
                provider.get_limit_up(trade_date),
                return_exceptions=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("TickFlow 取数异常: %s", e)
            return None

        # 异常转 None
        indices = None if isinstance(indices, Exception) else indices
        volume = None if isinstance(volume, Exception) else volume
        statistics = None if isinstance(statistics, Exception) else statistics
        sectors = None if isinstance(sectors, Exception) else sectors
        limit_up = None if isinstance(limit_up, Exception) else limit_up

        # 核心（volume/statistics）必须可用，否则 fallback
        if volume is None or statistics is None:
            logger.info("TickFlow 核心数据不全，fallback 原源")
            return None

        return {
            "indices": self._tf_indices_to_dict(indices),
            "volume": {
                "sh_volume": volume.sh_volume or 0,
                "sz_volume": volume.sz_volume or 0,
                "total_volume": volume.total_volume or 0,
            },
            "statistics": {
                "up_count": statistics.up_count,
                "down_count": statistics.down_count,
                "flat_count": statistics.flat_count,
            },
            "sectors": self._tf_sectors_to_dict(sectors),
            "limit_up": self._tf_limit_up_to_list(limit_up),
            "fetch_time": datetime.now().isoformat(),
            "breadth_quality": {
                "volume": {
                    "status": "ok",
                    "source": "tickflow",
                    "actual_count": 1,
                    "expected_count": 1,
                },
                "statistics": {
                    "status": "ok",
                    "source": "tickflow",
                    "actual_count": 1,
                    "expected_count": 1,
                },
            },
            "limit_up_quality": {
                "source_type": "tickflow",
                "status": "ok" if limit_up else "empty",
            },
        }

    @staticmethod
    def _tf_indices_to_dict(indices) -> dict[str, Any]:
        """{sh/sz/cy: IndexQuote} → 扁平 {sh_index_*, sz_index_*, cy_index_*}。"""
        if not indices:
            return {}
        result: dict[str, Any] = {}
        for key, q in indices.items():
            result[f"{key}_index_name"] = q.name
            result[f"{key}_index_price"] = q.price
            result[f"{key}_index_change"] = q.change
        return result

    @staticmethod
    def _tf_sectors_to_dict(sectors) -> dict[str, list]:
        """SectorResult → {top_sectors, bottom_sectors}（change 小数）。"""
        if not sectors:
            return {"top_sectors": [], "bottom_sectors": []}

        def to_rows(rows):
            return [
                {"name": r.sector_name, "code": r.sector_code, "change": r.change_pct}
                for r in rows
            ]

        return {
            "top_sectors": to_rows(sectors.top_sectors),
            "bottom_sectors": to_rows(sectors.bottom_sectors),
        }

    @staticmethod
    def _tf_limit_up_to_list(limit_up) -> list[dict[str, Any]]:
        """[LimitUpRow] → [{name, code, change}]（change 小数）。"""
        if not limit_up:
            return []
        return [
            {"name": r.stock_name, "code": r.stock_code, "change": r.change_pct}
            for r in limit_up
        ]
