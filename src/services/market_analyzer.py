"""市场分析服务 - 生成 A 股市场总结。"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import chinese_calendar as calendar

from src.api.finance import FinanceClient, FinanceAPIError
from src.models.schema import Article, MarketSummary
from src.services import trade_calendar as _tc
from src.storage.database import Database, CRUDOperations

logger = logging.getLogger(__name__)

# 新闻聚合结果结构
NewsAggregationResult = dict[str, Any]

OUTPUT_DIR = Path("output/market_summaries")


class MarketAnalyzer:
    """市场分析服务。

    提供交易日判断、数据收集、总结生成等功能。
    """

    def __init__(self, db: Database, finance_client: FinanceClient | None = None) -> None:
        """初始化市场分析服务。

        Args:
            db: 数据库实例
            finance_client: 财经数据客户端（可选，默认创建新实例）
        """
        self.db = db
        self.finance_client = finance_client or FinanceClient()
        self._summary_crud = CRUDOperations(MarketSummary)
        self._article_crud = CRUDOperations(Article)

        # 添加缓存服务
        from src.services.market_data_cache_service import MarketDataCacheService
        self._cache_service = MarketDataCacheService(self.db, self.finance_client)

    def is_trade_day(self, check_date: date | None = None) -> bool:
        """判断是否为 A 股交易日。

        保守规则（排除调休工作日周末）：
        - 周末一律不是交易日（即使调休上班日）
        - 法定节假日不是交易日

        Args:
            check_date: 待判断日期，默认为今天

        Returns:
            是否为交易日
        """
        return _tc.is_trade_day(check_date)

    def get_next_trade_date(self, trade_date: date) -> date:
        """获取下一个交易日。

        Args:
            trade_date: 当前交易日

        Returns:
            下一个交易日

        Raises:
            ValueError: 30 天内未找到下一个交易日
        """
        check_date = trade_date + timedelta(days=1)
        for _ in range(30):
            if self.is_trade_day(check_date):
                return check_date
            check_date += timedelta(days=1)
        raise ValueError(f"30 天内未找到下一个交易日: {trade_date}")

    def get_previous_trade_date(self, trade_date: date) -> date:
        """获取上一个交易日。

        Args:
            trade_date: 当前交易日

        Returns:
            上一个交易日

        Raises:
            ValueError: 30 天内未找到上一个交易日
        """
        return _tc.get_previous_trade_date(trade_date)

    def calculate_article_time_window(self, trade_date: date) -> tuple[datetime, datetime]:
        """计算文章时间窗口。

        精确窗口: trade_date 15:00 ~ next_trading_date 09:15

        Args:
            trade_date: 交易日期

        Returns:
            (start_datetime, end_datetime) 时间窗口
        """
        next_trade_date = self.get_next_trade_date(trade_date)
        start = datetime.combine(trade_date, datetime.min.time().replace(hour=15, minute=0))
        end = datetime.combine(next_trade_date, datetime.min.time().replace(hour=9, minute=15))
        return start, end

    def calculate_watch_time_window(self, trade_date: date) -> tuple[datetime, datetime]:
        """计算看盘数据时间窗口。

        看盘窗口: trade_date 09:00 ~ trade_date 15:00

        Args:
            trade_date: 交易日期

        Returns:
            (start_datetime, end_datetime) 时间窗口
        """
        start = datetime.combine(trade_date, datetime.min.time().replace(hour=9, minute=0))
        end = datetime.combine(trade_date, datetime.min.time().replace(hour=15, minute=0))
        return start, end

    def calculate_telegraph_time_window(self, trade_date: date) -> tuple[datetime, datetime]:
        """计算电报时间窗口。

        电报窗口: trade_date 09:00 ~ next_trade_date 09:15

        Args:
            trade_date: 交易日期

        Returns:
            (start_datetime, end_datetime) 时间窗口
        """
        next_trade_date = self.get_next_trade_date(trade_date)
        start = datetime.combine(trade_date, datetime.min.time().replace(hour=9, minute=0))
        end = datetime.combine(next_trade_date, datetime.min.time().replace(hour=9, minute=15))
        return start, end

    def get_latest_trade_date(self, target_date: date | None = None) -> date:
        """获取最近的交易日。

        智能判断逻辑:
        - 交易日 09:00 前 -> 返回上一个交易日(市场尚未开市)
        - 交易日 09:00 后 -> 返回今天
        - 非交易日 -> 返回最近交易日(往前回溯)

        Args:
            target_date: 目标日期, 默认为今天

        Returns:
            最近的交易日
        """
        if target_date is None:
            target_date = date.today()

        # 非交易日: 往前找最近的交易日
        if not self.is_trade_day(target_date):
            check_date = target_date - timedelta(days=1)
            for _ in range(30):
                if self.is_trade_day(check_date):
                    logger.info(f"非交易日 {target_date}, 回退到最近交易日: {check_date}")
                    return check_date
                check_date -= timedelta(days=1)
            logger.warning(f"30 天内未找到交易日, 使用 {target_date}")
            return target_date

        # 今天是交易日: 判断是否开盘前
        if target_date == date.today():
            now = datetime.now()
            market_open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)

            if now < market_open_time:
                try:
                    prev = self.get_previous_trade_date(target_date)
                    logger.info(f"市场尚未开市({now.strftime('%H:%M')}), 使用上一个交易日: {prev}")
                    return prev
                except ValueError:
                    logger.warning(f"未找到上一个交易日, 使用 {target_date}")
                    return target_date

            return target_date

        # 交易日且非今天
        return target_date

    def _is_historical_trade_date(self, trade_date: date) -> bool:
        """判断是否为历史交易日（早于当前可用交易日）。"""
        current_trade_date = self.get_latest_trade_date()
        return trade_date < current_trade_date

    def _missing_global_market_context(self, trade_date: date, message: str) -> dict[str, Any]:
        """构建海外市场上下文不可用的标准化占位结构。"""
        return {
            "status": "error",
            "target_a_trade_date": trade_date.isoformat(),
            "captured_at": None,
            "as_of": None,
            "session": None,
            "source": "none",
            "message": message,
            "source_attempts": [],
            "degraded": False,
            "us_market": {
                "status": "error",
                "session": None,
                "as_of": None,
                "indices": [],
                "risk_signals": {},
                "leaders": [],
                "source": "none",
                "message": message,
            },
        }

    def _global_context_is_cache_miss(self, context: Any) -> bool:
        if not isinstance(context, dict):
            return True
        return context.get("source") == "cache" and context.get("status") == "error"

    async def _attach_live_global_market_context(
        self,
        trade_date: date,
        market_data: dict[str, Any],
        *,
        cache_after_fetch: bool,
    ) -> dict[str, Any]:
        """为在线当前交易日市场数据补充海外市场上下文。"""
        try:
            context = await self.finance_client.get_global_market_context(trade_date)
        except Exception as e:
            logger.warning("获取海外市场上下文失败: %s", e)
            context = self._missing_global_market_context(
                trade_date,
                f"海外市场上下文获取失败: {e}",
            )

        market_data["global_market_context"] = context

        if cache_after_fetch:
            try:
                await self._cache_service.save_market_data(trade_date, market_data)
                logger.info("已缓存海外市场上下文: %s", trade_date)
            except Exception as e:
                logger.warning("海外市场上下文缓存写入失败: %s", e)

        return market_data

    async def collect_market_data(
        self,
        offline: bool = False,
        trade_date: date | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """收集市场数据。

        数据源策略:
        - 当前交易日: 缓存优先，缓存缺失则从 API 获取
        - 历史交易日: 只从缓存获取，无缓存则明确报告不可用
        - force=True: 仅对当前交易日跳过缓存；历史日期不支持强制刷新
        - offline=True: 只读取本地缓存，不触发任何网络请求

        Args:
            offline: 是否仅使用本地数据
            trade_date: 交易日期（可选）
            force: 是否强制刷新（跳过缓存）

        Returns:
            市场数据字典
        """
        if trade_date is None:
            trade_date = self.get_latest_trade_date()

        cache_service = self._cache_service
        is_historical = self._is_historical_trade_date(trade_date)

        # ========== 离线模式 ==========
        if offline:
            logger.info(f"离线模式: 仅使用本地缓存数据 ({trade_date})")
            cached_data = await cache_service.get_cached(trade_date)
            if cached_data:
                cached_data["offline"] = True
                cached_data["data_source"] = "cache"
                cached_data.setdefault(
                    "global_market_context",
                    self._missing_global_market_context(trade_date, "无可用海外市场上下文缓存"),
                )
                logger.info(f"离线模式命中缓存: {trade_date}")
                return cached_data
            else:
                logger.warning(f"离线模式: 无可用本地市场数据 ({trade_date})")
                return {
                    "indices": {},
                    "volume": {},
                    "statistics": {},
                    "sectors": {},
                    "limit_up": [],
                    "fetch_time": datetime.now().isoformat(),
                    "global_market_context": self._missing_global_market_context(
                        trade_date,
                        "离线模式: 无可用海外市场上下文缓存",
                    ),
                    "offline": True,
                    "data_source": "none",
                    "error": "离线模式: 无可用本地市场数据",
                }

        # ========== 历史交易日（仅缓存） ==========
        if is_historical:
            logger.info(f"历史交易日: 仅使用缓存数据 ({trade_date})")
            cached_data = await cache_service.get_cached(trade_date)
            if cached_data:
                cached_data["data_source"] = "cache"
                cached_data.setdefault(
                    "global_market_context",
                    self._missing_global_market_context(trade_date, "无可用海外市场上下文缓存"),
                )
                logger.info(f"历史交易日缓存命中: {trade_date}")
                return cached_data

            msg = (
                f"历史交易日 {trade_date} 无可用市场数据（无缓存且无历史数据源）。"
                f" 请先运行 wchat ai market-data backfill --date {trade_date} 回填市场数据"
            )
            if force:
                msg = (
                    f"历史交易日 {trade_date} 不支持强制刷新（无历史数据源）。"
                    f" 请先运行 wchat ai market-data backfill --date {trade_date} 回填市场数据"
                )
            logger.warning(msg)
            return {
                "indices": {},
                "volume": {},
                "statistics": {},
                "sectors": {},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
                "global_market_context": self._missing_global_market_context(
                    trade_date,
                    msg,
                ),
                "data_source": "none",
                "error": msg,
            }

        # ========== 当前交易日 - 强制刷新模式 ==========
        if force:
            logger.info(f"强制刷新模式: 跳过缓存，直接获取在线数据 ({trade_date})")
            try:
                market_data = await self.finance_client.get_all_market_data(trade_date=trade_date)
                await self._attach_live_global_market_context(
                    trade_date,
                    market_data,
                    cache_after_fetch=False,
                )

                if cache_service.should_cache(trade_date):
                    await cache_service.save_market_data(trade_date, market_data)
                    logger.info(f"已覆盖缓存: {trade_date}")

                market_data["data_source"] = "api"
                return market_data
            except Exception as e:
                logger.error(f"获取在线数据失败: {e}")
                return {
                    "indices": {},
                    "volume": {},
                    "statistics": {},
                    "sectors": {},
                    "limit_up": [],
                    "fetch_time": datetime.now().isoformat(),
                    "global_market_context": self._missing_global_market_context(
                        trade_date,
                        f"海外市场上下文不可用: {e}",
                    ),
                    "data_source": "error",
                    "error": str(e),
                }

        # ========== 当前交易日 - 缓存优先模式 ==========
        cached_data = await cache_service.get_cached(trade_date)
        if cached_data:
            logger.info(f"缓存命中: {trade_date}")
            cached_data["data_source"] = "cache"
            if self._global_context_is_cache_miss(cached_data.get("global_market_context")):
                await self._attach_live_global_market_context(
                    trade_date,
                    cached_data,
                    cache_after_fetch=cache_service.should_cache(trade_date),
                )
            return cached_data

        # 缓存未命中，从 API 获取
        logger.info(f"缓存未命中，从 API 获取: {trade_date}")
        try:
            market_data = await self.finance_client.get_all_market_data(trade_date=trade_date)
            await self._attach_live_global_market_context(
                trade_date,
                market_data,
                cache_after_fetch=False,
            )

            if cache_service.should_cache(trade_date):
                await cache_service.save_market_data(trade_date, market_data)
                logger.info(f"已缓存市场数据: {trade_date}")

            market_data["data_source"] = "api"
            return market_data
        except Exception as e:
            logger.error(f"获取在线数据失败: {e}")
            return {
                "indices": {},
                "volume": {},
                "statistics": {},
                "sectors": {},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
                "global_market_context": self._missing_global_market_context(
                    trade_date,
                    f"海外市场上下文不可用: {e}",
                ),
                "data_source": "error",
                "error": str(e),
            }

    async def collect_news_data(
        self,
        trade_date: date,
        offline: bool = False,
        *,
        prepare_article_evidence: bool = False,
        force_evidence: bool = False,
    ) -> NewsAggregationResult:
        """聚合新闻数据（财联社电报、看盘数据、相关文章）。

        单一新闻源缺失时仍可继续生成总结。

        Args:
            trade_date: 交易日期
            offline: 是否仅使用本地数据
            prepare_article_evidence: 是否自动准备文章证据
            force_evidence: 是否强制刷新文章证据（忽略缓存）

        Returns:
            新闻聚合结果:
            {
                "status": "success" | "degraded" | "failed",
                "telegraphs": [...],
                "watch_items": [...],
                "articles": [...],
                "article_evidence": [...],   # 结构化文章证据（可选）
                "sources_status": {...},
                "source_details": {...},
                "article_evidence_diagnostics": {...},  # 证据准备诊断（可选）
                "time_windows": {...},
            }
        """
        # 计算各资料类型的时间窗口
        watch_window = self.calculate_watch_time_window(trade_date)
        telegraph_window = self.calculate_telegraph_time_window(trade_date)
        article_window = self.calculate_article_time_window(trade_date)

        result: NewsAggregationResult = {
            "telegraphs": [],
            "watch_items": [],
            "articles": [],
            "sources_status": {
                "telegraphs": "empty",
                "watch_items": "empty",
                "articles": "empty",
            },
            "source_details": {
                "telegraphs": {},
                "watch_items": {},
                "articles": {},
            },
            "time_windows": {
                "watch": {
                    "start": watch_window[0].strftime("%Y-%m-%d %H:%M"),
                    "end": watch_window[1].strftime("%Y-%m-%d %H:%M"),
                },
                "telegraph": {
                    "start": telegraph_window[0].strftime("%Y-%m-%d %H:%M"),
                    "end": telegraph_window[1].strftime("%Y-%m-%d %H:%M"),
                },
                "article": {
                    "start": article_window[0].strftime("%Y-%m-%d %H:%M"),
                    "end": article_window[1].strftime("%Y-%m-%d %H:%M"),
                },
            },
            # 保留 time_window 兼容旧接口
            "time_window": {
                "start": article_window[0].strftime("%Y-%m-%d %H:%M"),
                "end": article_window[1].strftime("%Y-%m-%d %H:%M"),
            },
        }

        # ========== 1. 收集财联社重要电报 ==========
        try:
            from src.services.cls_telegraph_service import CLSTelegraphService

            telegraph_service = CLSTelegraphService(self.db)

            # 使用电报专用窗口: trade_date 09:00 ~ next_trade_date 09:15
            start_dt, end_dt = telegraph_window

            start_time = int(start_dt.timestamp())
            end_time = int(end_dt.timestamp())
            telegraphs = await telegraph_service.list_telegraphs(
                start_time=start_time,
                end_time=end_time,
                min_level="B",  # 只获取 B 级以上重要电报
                limit=100,
            )

            if telegraphs:
                result["telegraphs"] = self._serialize_telegraphs(telegraphs)
                result["sources_status"]["telegraphs"] = "ok"
                result["source_details"]["telegraphs"] = {
                    "mode": "local",
                    "message": f"已获取 {len(telegraphs)} 条",
                }
                logger.info(f"获取财联社电报: {len(telegraphs)} 条")
            else:
                if offline:
                    result["sources_status"]["telegraphs"] = "empty"
                    result["source_details"]["telegraphs"] = {
                        "mode": "offline_empty",
                        "message": "0 条",
                    }
                    logger.info(f"财联社电报: 无数据 ({trade_date})")
                else:
                    ingest_result = await telegraph_service.ingest_telegraphs_with_status(
                        start_time=start_time,
                        end_time=end_time,
                    )
                    if ingest_result.get("status") == "error":
                        result["sources_status"]["telegraphs"] = "error"
                        result["source_details"]["telegraphs"] = {
                            "mode": "auto_fetch_error",
                            "message": "自动补抓失败",
                            "fetch_result": ingest_result,
                        }
                    else:
                        telegraphs = await telegraph_service.list_telegraphs(
                            start_time=start_time,
                            end_time=end_time,
                            min_level="B",
                            limit=100,
                        )
                        if telegraphs:
                            result["telegraphs"] = self._serialize_telegraphs(telegraphs)
                            result["sources_status"]["telegraphs"] = "ok"
                            result["source_details"]["telegraphs"] = {
                                "mode": "auto_fetch_ok",
                                "message": f"已获取 {len(telegraphs)} 条（自动补抓）",
                                "fetch_result": ingest_result,
                            }
                            logger.info(f"获取财联社电报: {len(telegraphs)} 条（自动补抓）")
                        else:
                            result["sources_status"]["telegraphs"] = "empty"
                            result["source_details"]["telegraphs"] = {
                                "mode": "auto_fetch_empty",
                                "message": "0 条（已自动抓取）",
                                "fetch_result": ingest_result,
                            }
                            logger.info(f"财联社电报: 自动补抓后仍无数据 ({trade_date})")

        except Exception as e:
            result["sources_status"]["telegraphs"] = "error"
            result["source_details"]["telegraphs"] = {
                "mode": "error",
                "message": "获取失败",
            }
            logger.warning(f"获取财联社电报失败: {e}")

        # ========== 2. 收集财联社看盘数据 ==========
        try:
            from src.services.cls_watch_service import CLSWatchService

            watch_service = CLSWatchService(self.db)

            # 使用看盘专用窗口: trade_date 09:00 ~ trade_date 15:00
            start_dt, end_dt = watch_window
            start_time = int(start_dt.timestamp())
            end_time = int(end_dt.timestamp())
            watch_items = await watch_service.get_watch_data_for_summary(
                trade_date,
                time_window=watch_window,
            )

            if watch_items:
                result["watch_items"] = watch_items
                result["sources_status"]["watch_items"] = "ok"
                result["source_details"]["watch_items"] = {
                    "mode": "local",
                    "message": f"已获取 {len(watch_items)} 条",
                }
                logger.info(f"获取财联社看盘数据: {len(watch_items)} 条")
            else:
                if offline:
                    result["sources_status"]["watch_items"] = "empty"
                    result["source_details"]["watch_items"] = {
                        "mode": "offline_empty",
                        "message": "0 条",
                    }
                    logger.info(f"财联社看盘数据: 无数据 ({trade_date})")
                else:
                    ingest_result = await watch_service.ingest_watch_data_with_status(
                        start_time=start_time,
                        end_time=end_time,
                    )
                    if ingest_result.get("status") == "error":
                        result["sources_status"]["watch_items"] = "error"
                        result["source_details"]["watch_items"] = {
                            "mode": "auto_fetch_error",
                            "message": "自动补抓失败",
                            "fetch_result": ingest_result,
                        }
                    else:
                        watch_items = await watch_service.get_watch_data_for_summary(
                            trade_date,
                            time_window=watch_window,
                        )
                        if watch_items:
                            result["watch_items"] = watch_items
                            result["sources_status"]["watch_items"] = "ok"
                            result["source_details"]["watch_items"] = {
                                "mode": "auto_fetch_ok",
                                "message": f"已获取 {len(watch_items)} 条（自动补抓）",
                                "fetch_result": ingest_result,
                            }
                            logger.info(f"获取财联社看盘数据: {len(watch_items)} 条（自动补抓）")
                        else:
                            result["sources_status"]["watch_items"] = "empty"
                            result["source_details"]["watch_items"] = {
                                "mode": "auto_fetch_empty",
                                "message": "0 条（已自动抓取）",
                                "fetch_result": ingest_result,
                            }
                            logger.info(f"财联社看盘数据: 自动补抓后仍无数据 ({trade_date})")

        except Exception as e:
            result["sources_status"]["watch_items"] = "error"
            result["source_details"]["watch_items"] = {
                "mode": "error",
                "message": "获取失败",
            }
            logger.warning(f"获取财联社看盘数据失败: {e}")

        # ========== 3. 收集相关市场文章（含 feed 元数据） ==========
        try:
            articles = await self.get_related_articles(
                trade_date, time_window=article_window, include_feed_metadata=True,
            )

            if articles:
                result["articles"] = articles
                result["sources_status"]["articles"] = "ok"
                result["source_details"]["articles"] = {
                    "mode": "local",
                    "message": f"已获取 {len(articles)} 篇",
                }
                logger.info(f"获取相关文章: {len(articles)} 篇")
            else:
                result["sources_status"]["articles"] = "empty"
                result["source_details"]["articles"] = {
                    "mode": "empty",
                    "message": "0 篇",
                }
                logger.info(f"相关文章: 无数据 ({trade_date})")

        except Exception as e:
            result["sources_status"]["articles"] = "error"
            result["source_details"]["articles"] = {
                "mode": "error",
                "message": "获取失败",
            }
            logger.warning(f"获取相关文章失败: {e}")

        # ========== 4. 自动准备文章证据（可选） ==========
        if prepare_article_evidence and result.get("articles"):
            result["article_evidence"] = []
            result["article_evidence_diagnostics"] = {}
            try:
                from src.services.article_evidence import ArticleEvidenceService

                evidence_service = ArticleEvidenceService(self.db)

                # 选择候选集
                candidates = self.select_evidence_candidates(result["articles"])

                # 离线模式：只复用缓存，不生成新证据
                if offline:
                    batch_result = await evidence_service.prepare_batch(
                        candidates, force=False,
                    )
                    # 离线模式标记：过滤掉 prepared 记录（不应有新调用）
                    # 但如果 AI 调用已经发生（缓存命中返回 reused），保留
                else:
                    batch_result = await evidence_service.prepare_batch(
                        candidates, force=force_evidence,
                    )

                result["article_evidence"] = [
                    r.to_dict() for r in batch_result.records
                ]
                result["article_evidence_diagnostics"] = batch_result.to_dict()

                logger.info(
                    "文章证据准备完成: prepared=%d, reused=%d, fallback=%d, failed=%d",
                    batch_result.prepared, batch_result.reused,
                    batch_result.fallback, batch_result.failed,
                )

            except Exception as e:
                logger.warning("文章证据准备失败（降级继续）: %s", e)
                result["article_evidence_diagnostics"] = {
                    "error": str(e),
                    "total": len(result.get("articles", [])),
                }

        # 计算聚合状态: success / degraded / failed
        statuses = list(result["sources_status"].values())
        error_count = statuses.count("error")
        if error_count == len(statuses):
            result["status"] = "failed"
        elif error_count > 0:
            result["status"] = "degraded"
        else:
            result["status"] = "success"

        return result

    @staticmethod
    def _serialize_telegraphs(telegraphs: list[Any]) -> list[dict[str, Any]]:
        """将电报 ORM 对象转为摘要结构。"""
        return [
            {
                "title": t.title,
                "content": t.content,
                "level": t.level,
                "ctime": t.ctime,
                "publish_time": datetime.fromtimestamp(t.ctime).strftime("%Y-%m-%d %H:%M") if t.ctime else None,
            }
            for t in telegraphs
        ]

    async def get_related_articles(
        self,
        trade_date: date,
        time_window: tuple[datetime, datetime] | None = None,
        *,
        include_feed_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        """获取与交易日相关的文章（精确时间窗口）。

        时间窗口: trade_date 15:00 ~ next_trading_date 09:15。
        如果未提供 time_window，则自动计算。

        Args:
            trade_date: 交易日期
            time_window: 精确时间窗口 (start, end)，如未提供则自动计算
            include_feed_metadata: 是否包含 feed 元数据（名称、权重、provider）

        Returns:
            文章列表（包含标题、摘要、内容，可选 feed 元数据）
        """
        if time_window is None:
            time_window = self.calculate_article_time_window(trade_date)

        start_dt, end_dt = time_window
        logger.info(f"文章时间窗口: {start_dt.strftime('%Y-%m-%d %H:%M')} ~ {end_dt.strftime('%Y-%m-%d %H:%M')}")

        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Article)
                .where(Article.publish_time >= start_dt)
                .where(Article.publish_time <= end_dt)
                .order_by(Article.publish_time.desc())
                .limit(50)
            )
            articles = result.scalars().all()

            # 批量加载 feed 元数据
            feed_map: dict[int, dict[str, Any]] = {}
            if include_feed_metadata:
                feed_ids = {a.feed_id for a in articles if a.feed_id}
                if feed_ids:
                    from src.models.schema import Feed
                    feed_result = await session.execute(
                        select(Feed).where(Feed.id.in_(feed_ids))
                    )
                    for feed in feed_result.scalars().all():
                        feed_map[feed.id] = {
                            "feed_name": feed.name or "",
                            "feed_weight": feed.weight if feed.weight is not None else 5,
                            "provider": feed.provider or "",
                        }

        article_dicts = []
        for a in articles:
            d: dict[str, Any] = {
                "id": a.id,
                "title": a.title,
                "summary": a.summary or "",
                "content": (a.content or "")[:1000] if a.content else "",
                "publish_time": a.publish_time.isoformat() if a.publish_time else None,
            }
            if include_feed_metadata and a.feed_id and a.feed_id in feed_map:
                d.update(feed_map[a.feed_id])
            elif include_feed_metadata:
                d["feed_name"] = ""
                d["feed_weight"] = 5
                d["provider"] = a.provider or ""
            article_dicts.append(d)

        return article_dicts

    @staticmethod
    def select_evidence_candidates(
        articles: list[dict[str, Any]],
        max_candidates: int = 10,
    ) -> list[dict[str, Any]]:
        """从文章列表中按市场相关度选择候选集。

        使用确定性信号排序：复盘 > 策略 > 主线 > 板块 > 情绪 > 涨停 > 风险。
        同时考虑 feed 权重作为次要排序因子。

        Args:
            articles: 文章列表（需包含 title, summary, content）
            max_candidates: 最大候选数

        Returns:
            排序后的候选文章列表
        """
        from src.services.article_evidence import compute_relevance_score

        scored: list[tuple[int, dict[str, Any]]] = []
        for a in articles:
            score = compute_relevance_score(
                title=a.get("title", ""),
                summary=a.get("summary", ""),
                content_available=bool(a.get("content")),
            )
            # feed 权重加成（0-10 → 0-10 分加成）
            weight = a.get("feed_weight", 5)
            score += weight
            scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:max_candidates]]

    @staticmethod
    def build_fallback_article_signals(
        articles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """当证据提取不可用时，从文章标题/摘要构建降级信号。

        Args:
            articles: 原始文章列表

        Returns:
            降级后的文章信号列表
        """
        fallback = []
        for a in articles[:10]:
            fallback.append({
                "title": a.get("title", ""),
                "summary": (a.get("summary") or "")[:200],
                "feed_name": a.get("feed_name", ""),
                "fallback": True,
            })
        return fallback

    async def save_summary(
        self,
        trade_date: date,
        content: str,
        data_sources: dict[str, Any],
        *,
        article_evidence_diagnostics: dict[str, Any] | None = None,
    ) -> MarketSummary:
        """保存市场总结。

        同时保存到文件和数据库。使用 upsert 模式：
        - 如果记录已存在，更新内容
        - 如果记录不存在，插入新记录
        - 先写文件再提交数据库，确保两者都成功

        Args:
            trade_date: 交易日期
            content: 总结内容
            data_sources: 数据来源信息

        Returns:
            保存的 MarketSummary 对象

        Raises:
            RuntimeError: 文件或数据库持久化失败
        """
        from sqlalchemy import select

        # 合并文章证据溯源到 data_sources
        save_sources = dict(data_sources) if data_sources else {}
        if article_evidence_diagnostics:
            save_sources["article_evidence_diagnostics"] = article_evidence_diagnostics

        # 1. 先保存到文件（非事务性，容易重试）
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            file_path = OUTPUT_DIR / f"{trade_date}.md"
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"市场总结文件已保存: {file_path}")
        except OSError as e:
            msg = f"市场总结文件保存失败: {e}"
            logger.error(msg)
            raise RuntimeError(msg) from e

        # 2. 再保存到数据库 (upsert 模式)
        async with self.db.get_session() as session:
            # 先查询是否存在
            result = await session.execute(
                select(MarketSummary).where(MarketSummary.trade_date == trade_date)
            )
            summary = result.scalar_one_or_none()

            if summary:
                # 更新已有记录
                summary.content = content
                summary.data_sources = json.dumps(save_sources, ensure_ascii=False)
                logger.info(f"更新已有市场总结: {trade_date}")
            else:
                # 插入新记录
                summary = MarketSummary(
                    trade_date=trade_date,
                    content=content,
                    data_sources=json.dumps(save_sources, ensure_ascii=False),
                )
                session.add(summary)
                logger.info(f"创建新市场总结: {trade_date}")

            await session.flush()
            await session.refresh(summary)

        return summary

    async def get_existing_summary(self, trade_date: date) -> MarketSummary | None:
        """获取已存在的市场总结。

        Args:
            trade_date: 交易日期

        Returns:
            已存在的总结，不存在返回 None
        """
        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(MarketSummary).where(MarketSummary.trade_date == trade_date)
            )
            return result.scalar_one_or_none()

    async def list_summaries(
        self,
        limit: int = 10,
    ) -> list[MarketSummary]:
        """获取历史市场总结列表。

        Args:
            limit: 返回数量

        Returns:
            总结列表
        """
        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(MarketSummary)
                .order_by(MarketSummary.trade_date.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    def _format_indices(self, indices: dict[str, Any]) -> str:
        """格式化指数数据。"""
        if not indices:
            return "数据获取失败"

        lines = []
        for key, data in indices.items():
            name = data.get("name", key)
            close = data.get("close", 0)
            change = data.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}: {close:.2f} ({sign}{change*100:.2f}%)")

        return "\n".join(lines)

    def _format_sectors(self, sectors: list[dict[str, Any]]) -> str:
        """格式化板块数据。"""
        if not sectors:
            return "无数据"

        lines = []
        for s in sectors:
            name = s.get("name", "")
            change = s.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}: {sign}{change*100:.2f}%")

        return "\n".join(lines)

    def _format_stocks(self, stocks: list[dict[str, Any]]) -> str:
        """格式化个股数据。"""
        if not stocks:
            return "无数据"

        lines = []
        for s in stocks:
            name = s.get("name", "")
            code = s.get("code", "")
            change = s.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}({code}): {sign}{change*100:.2f}%")

        return "\n".join(lines)

    def _format_articles(self, articles: list[dict[str, Any]]) -> str:
        """格式化文章数据。"""
        if not articles:
            return "无相关文章"

        lines = []
        for a in articles:
            title = a.get("title", "")
            summary = a.get("summary", "")[:100] if a.get("summary") else ""
            lines.append(f"- **{title}**")
            if summary:
                lines.append(f"  {summary}...")

        return "\n".join(lines)
