"""MarketDataCacheService 单元测试。"""

import pytest
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from src.models.schema import MarketSector, LimitUpStock

from src.services.market_data_cache_service import MarketDataCacheService, MARKET_CLOSE_TIME


@pytest.fixture
def sample_data() -> dict:
    """标准市场数据样本。"""
    return {
        "indices": {
            "sh": {"name": "上证指数", "close": 3000.0, "change": 0.01},
            "sz": {"name": "深证成指", "close": 10000.0, "change": -0.02},
            "cy": {"name": "创业板指", "close": 2000.0, "change": 0.03},
        },
        "volume": {
            "sh_volume": 3000.0,
            "sz_volume": 4000.0,
            "total_volume": 7000.0,
        },
        "statistics": {
            "up_count": 2000,
            "down_count": 2000,
            "flat_count": 500,
        },
        "sectors": {
            "top_sectors": [
                {"code": "BK001", "name": "板块A", "change": 0.05},
                {"code": "BK002", "name": "板块B", "change": 0.03},
            ],
            "bottom_sectors": [
                {"code": "BK003", "name": "板块C", "change": -0.04},
            ],
        },
        "limit_up": [
            {"code": "000001", "name": "股票A", "change": 0.10, "limit_days": 2, "industry": "科技"},
            {"code": "000002", "name": "股票B", "change": 0.10, "limit_days": 1, "industry": "金融"},
        ],
        "global_market_context": {
            "status": "ok",
            "target_a_trade_date": "2026-03-27",
            "captured_at": "2026-03-27T22:30:00+08:00",
            "as_of": "2026-03-27T22:29:00+08:00",
            "session": "regular",
            "source": "yahoo_quote",
            "us_market": {
                "status": "ok",
                "session": "regular",
                "as_of": "2026-03-27T22:29:00+08:00",
                "indices": [
                    {"symbol": "DJIA", "name": "道琼斯工业平均指数", "price": 39000.0, "change_pct": 0.004},
                    {"symbol": "SPX", "name": "标普500", "price": 5200.0, "change_pct": 0.006},
                    {"symbol": "IXIC", "name": "纳斯达克综合指数", "price": 16500.0, "change_pct": 0.009},
                ],
                "risk_signals": {
                    "vix": {"name": "VIX波动率指数", "value": 13.5, "change_pct": -0.02},
                },
                "leaders": [],
                "source": "yahoo_quote",
            },
        },
    }


class TestShouldCache:
    """测试 should_cache 方法。"""

    def test_historical_date_should_cache(self):
        """历史日期应该缓存。"""
        service = MagicMock(spec=MarketDataCacheService)
        service.should_cache = MarketDataCacheService.should_cache.__get__(service, MarketDataCacheService)

        # 昨天
        yesterday = date.today() - timedelta(days=1)
        assert service.should_cache(yesterday) is True

        # 一周前
        week_ago = date.today() - timedelta(days=7)
        assert service.should_cache(week_ago) is True

    def test_today_before_market_close_should_not_cache(self):
        """今天收盘前不应该缓存。"""
        service = MagicMock(spec=MarketDataCacheService)
        service.should_cache = MarketDataCacheService.should_cache.__get__(service, MarketDataCacheService)

        today = date.today()

        # 模拟收盘前的时间
        with patch('src.services.market_data_cache_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.combine(today, time(10, 30))
            mock_dt.date.side_effect = date
            assert service.should_cache(today) is False

    def test_today_after_market_close_should_cache(self):
        """今天收盘后应该缓存。"""
        service = MagicMock(spec=MarketDataCacheService)
        service.should_cache = MarketDataCacheService.should_cache.__get__(service, MarketDataCacheService)

        today = date.today()

        # 模拟收盘后的时间
        with patch('src.services.market_data_cache_service.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.combine(today, time(16, 0))
            mock_dt.date.side_effect = date
            assert service.should_cache(today) is True


class TestGetCached:
    """测试 get_cached 方法。"""

    @pytest.mark.asyncio
    async def test_get_cached_returns_none_when_no_cache(self):
        """无缓存时返回 None。"""
        mock_db = MagicMock()
        mock_session = AsyncMock()
        query_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        mock_session.execute = AsyncMock(side_effect=query_results)

        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        service = MarketDataCacheService(mock_db)
        result = await service.get_cached(date.today())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_returns_data_when_exists(self):
        """有缓存时返回数据。"""
        from src.models.schema import MarketIndex, MarketVolume, MarketStatistics, MarketSector, LimitUpStock

        mock_db = MagicMock()
        mock_session = AsyncMock()

        trade_date = date.today()

        # 模拟指数数据
        mock_index = MarketIndex(
            trade_date=trade_date,
            sh_index_name="上证指数",
            sh_index_price=3000.0,
            sh_index_change=0.01,
        )

        # 模拟成交额数据
        mock_volume = MarketVolume(
            trade_date=trade_date,
            sh_volume=3000.0,
            sz_volume=4000.0,
            total_volume=7000.0,
        )

        # 模拟涨跌统计数据
        mock_stats = MarketStatistics(
            trade_date=trade_date,
            up_count=2000,
            down_count=2000,
            flat_count=500,
        )

        # 模拟板块数据
        mock_sector = MarketSector(
            trade_date=trade_date,
            sector_code="BK001",
            sector_name="测试板块",
            change_pct=2.5,
        )

        # 模拟涨停股数据
        mock_stock = LimitUpStock(
            trade_date=trade_date,
            stock_code="000001",
            stock_name="测试股票",
            change_pct=10.0,
            limit_days=2,
        )

        # 设置查询返回
        def mock_execute(query):
            result = MagicMock()
            # 根据查询的表返回不同的数据
            if "market_indices" in str(query):
                result.scalar_one_or_none.return_value = mock_index
            elif "market_volume" in str(query):
                result.scalar_one_or_none.return_value = mock_volume
            elif "market_statistics" in str(query):
                result.scalar_one_or_none.return_value = mock_stats
            elif "market_sectors" in str(query):
                result.scalars.return_value.all.return_value = [mock_sector]
            elif "limit_up_stocks" in str(query):
                result.scalars.return_value.all.return_value = [mock_stock]
            elif "global_market_contexts" in str(query):
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        service = MarketDataCacheService(mock_db)
        result = await service.get_cached(trade_date)

        # 验证返回的数据结构
        assert result is not None
        assert "indices" in result
        assert "volume" in result
        assert "statistics" in result
        assert result["global_market_context"]["status"] == "error"


class TestSaveMarketData:
    """测试 save_market_data 方法。"""

    @pytest.mark.asyncio
    async def test_save_market_data_stores_all_types(self):
        """保存所有类型的数据。"""
        mock_db = MagicMock()
        mock_session = AsyncMock()
        # 所有查询返回 None（无已存在记录 → insert 路径）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        service = MarketDataCacheService(mock_db)

        trade_date = date.today()
        data = {
            "indices": {
                "sh": {"name": "上证指数", "close": 3000.0, "change": 0.01},
            },
            "volume": {
                "sh_volume": 3000.0,
                "sz_volume": 4000.0,
                "total_volume": 7000.0,
            },
            "statistics": {
                "up_count": 2000,
                "down_count": 2000,
                "flat_count": 500,
            },
            "sectors": {
                "top_sectors": [
                    {"code": "BK001", "name": "测试板块", "change": 0.025}
                ]
            },
            "limit_up": [
                {"code": "000001", "name": "测试股票", "change": 0.1, "limit_days": 2, "industry": "科技"}
            ],
        }

        await service.save_market_data(trade_date, data)

        # 验证 session.add 被调用（insert 路径）
        assert mock_session.add.call_count >= 3
        assert mock_session.commit.called


class TestDeleteCache:
    """测试 delete_cache 方法。"""

    @pytest.mark.asyncio
    async def test_delete_cache_removes_all_data_types(self):
        """删除所有类型的缓存数据。"""
        mock_db = MagicMock()
        mock_session = AsyncMock()

        # 模拟删除结果
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        service = MarketDataCacheService(mock_db)
        deleted_count = await service.delete_cache(date.today())

        # 验证删除了 6 种数据类型
        assert mock_session.execute.call_count == 6
        assert mock_session.commit.called
        assert deleted_count >= 0


class TestSaveMarketDataUpsertIntegration:
    """数据库级测试：验证 save_market_data 的 upsert 幂等性。"""

    @pytest.mark.asyncio
    async def test_save_twice_same_trade_date_no_error(self, integration_db, sample_data):
        """同一交易日连续保存两次不会抛出 UNIQUE constraint 错误。"""
        from src.storage.database import Database

        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次保存
        await service.save_market_data(trade_date, sample_data)

        # 第二次保存 — 不应抛出异常
        await service.save_market_data(trade_date, sample_data)

    @pytest.mark.asyncio
    async def test_repeated_save_overwrites_values(self, integration_db, sample_data):
        """重复保存会覆盖已有值而不是插入重复行。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次保存
        await service.save_market_data(trade_date, sample_data)

        # 构造更新后的数据
        updated_data = {
            **sample_data,
            "indices": {
                "sh": {"name": "上证指数", "close": 3100.0, "change": 0.02},
                "sz": {"name": "深证成指", "close": 10500.0, "change": -0.01},
                "cy": {"name": "创业板指", "close": 2100.0, "change": 0.04},
            },
            "volume": {
                "sh_volume": 3500.0,
                "sz_volume": 4500.0,
                "total_volume": 8000.0,
            },
            "statistics": {
                "up_count": 2500,
                "down_count": 1500,
                "flat_count": 600,
            },
        }

        # 第二次保存
        await service.save_market_data(trade_date, updated_data)

        # 验证缓存中的值已更新
        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["indices"]["sh"]["close"] == 3100.0
        assert cached["volume"]["total_volume"] == 8000.0
        assert cached["statistics"]["up_count"] == 2500

    @pytest.mark.asyncio
    async def test_repeated_save_sectors_no_duplicates(self, integration_db, sample_data):
        """重复保存板块数据不会产生重复行。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        await service.save_market_data(trade_date, sample_data)
        await service.save_market_data(trade_date, sample_data)

        # 直接查询数据库验证不重复（格式化层 top/bottom 切片可能有重叠）
        from sqlalchemy import func as sa_func
        async with integration_db.get_session() as session:
            result = await session.execute(
                select(MarketSector).where(MarketSector.trade_date == trade_date)
            )
            sectors = result.scalars().all()

        sector_codes = [s.sector_code for s in sectors]
        assert len(sector_codes) == 3  # 只应有 3 个不重复的板块
        assert len(sector_codes) == len(set(sector_codes))

    @pytest.mark.asyncio
    async def test_repeated_save_limit_up_no_duplicates(self, integration_db, sample_data):
        """重复保存涨停股数据不会产生重复行。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        await service.save_market_data(trade_date, sample_data)
        await service.save_market_data(trade_date, sample_data)

        # 验证涨停股不重复
        cached = await service.get_cached(trade_date)
        assert cached is not None
        all_stock_codes = [s["code"] for s in cached["limit_up"]]
        assert len(all_stock_codes) == len(set(all_stock_codes))

    @pytest.mark.asyncio
    async def test_repeated_save_overwrites_sector_values(self, integration_db, sample_data):
        """重复保存板块数据会覆盖已有值。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        await service.save_market_data(trade_date, sample_data)

        # 更新板块数据（相同 code，不同 change）
        updated_data = {
            **sample_data,
            "sectors": {
                "top_sectors": [
                    {"code": "BK001", "name": "板块A", "change": 0.08},
                ],
                "bottom_sectors": [],
            },
        }
        await service.save_market_data(trade_date, updated_data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        top_sectors = cached["sectors"]["top_sectors"]
        bk001 = next(s for s in top_sectors if s["code"] == "BK001")
        assert bk001["change"] == pytest.approx(0.08)


class TestGlobalMarketContextCache:
    """测试海外市场上下文缓存。"""

    @pytest.mark.asyncio
    async def test_save_and_read_global_market_context(self, integration_db, sample_data):
        """保存市场数据时应同时保存海外市场上下文，并以同结构读回。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        await service.save_market_data(trade_date, sample_data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        context = cached["global_market_context"]
        assert context["status"] == "ok"
        assert context["target_a_trade_date"] == "2026-03-27"
        assert context["session"] == "regular"
        assert context["us_market"]["indices"][0]["symbol"] == "DJIA"

    @pytest.mark.asyncio
    async def test_global_market_context_upsert_overwrites_payload(self, integration_db, sample_data):
        """重复保存同一交易日时，海外市场上下文质量相同时按目标交易日覆盖。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        await service.save_market_data(trade_date, sample_data)

        updated_context = {
            **sample_data["global_market_context"],
            "message": "更新后的消息",
            "us_market": {
                **sample_data["global_market_context"]["us_market"],
                "indices": sample_data["global_market_context"]["us_market"]["indices"][:1],
            },
        }
        await service.save_market_data(trade_date, {
            **sample_data,
            "global_market_context": updated_context,
        })

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["global_market_context"]["status"] == "ok"
        assert len(cached["global_market_context"]["us_market"]["indices"]) == 1

    @pytest.mark.asyncio
    async def test_missing_global_market_context_cache_is_explicit(self, integration_db, sample_data):
        """有 A 股缓存但没有海外上下文时，应返回显式缺失状态。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data_without_context = dict(sample_data)
        data_without_context.pop("global_market_context")
        await service.save_market_data(trade_date, data_without_context)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["global_market_context"]["status"] == "error"
        assert cached["global_market_context"]["source"] == "cache"
        assert "无可用海外市场上下文缓存" in cached["global_market_context"]["message"]


class TestBreadthQualityCacheProtection:
    """测试宽度数据质量状态对缓存写入的保护。"""

    @pytest.mark.asyncio
    async def test_ok_breadth_writes_volume_and_statistics(self, integration_db, sample_data):
        """breadth_quality 为 ok 时，成交额和涨跌统计应正常写库。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "ok", "source": "eastmoney_curl"},
                "statistics": {"status": "ok", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["volume"]["total_volume"] == 7000.0
        assert cached["statistics"]["up_count"] == 2000

    @pytest.mark.asyncio
    async def test_ok_breadth_with_official_and_pytdx_sources_still_writes(self, integration_db, sample_data):
        """breadth_quality source 切换为 official / pytdx 时，缓存门控仍只看 status。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "ok", "source": "official_exchange_turnover"},
                "statistics": {"status": "ok", "source": "pytdx_quotes"},
            },
        }
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["volume"]["total_volume"] == 7000.0
        assert cached["statistics"]["up_count"] == 2000

    @pytest.mark.asyncio
    async def test_error_breadth_skips_volume_and_statistics_write(self, integration_db, sample_data):
        """breadth_quality 为 error 时，成交额和涨跌统计不应写库。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "error", "source": "eastmoney_curl"},
                "statistics": {"status": "error", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        # 成交额和涨跌统计不应写入
        assert cached["volume"]["total_volume"] == 0
        assert cached["statistics"]["up_count"] == 0

    @pytest.mark.asyncio
    async def test_partial_breadth_skips_volume_and_statistics_write(self, integration_db, sample_data):
        """breadth_quality 为 partial 时，成交额和涨跌统计不应写库。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "partial", "source": "eastmoney_curl"},
                "statistics": {"status": "partial", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["volume"]["total_volume"] == 0
        assert cached["statistics"]["up_count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_breadth_does_not_overwrite_existing_cache(self, integration_db, sample_data):
        """后续无效宽度数据不应覆盖已有有效缓存。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次：写入有效数据
        ok_data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "ok", "source": "eastmoney_curl"},
                "statistics": {"status": "ok", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, ok_data)

        # 第二次：尝试写入无效数据
        error_data = {
            **sample_data,
            "volume": {"sh_volume": 0, "sz_volume": 0, "total_volume": 0},
            "statistics": {"up_count": 0, "down_count": 0, "flat_count": 0},
            "breadth_quality": {
                "volume": {"status": "error", "source": "eastmoney_curl"},
                "statistics": {"status": "error", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, error_data)

        # 验证：原有效数据未被覆盖
        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["volume"]["total_volume"] == 7000.0
        assert cached["statistics"]["up_count"] == 2000

    @pytest.mark.asyncio
    async def test_missing_breadth_quality_still_writes(self, integration_db, sample_data):
        """缺少 breadth_quality 时（向后兼容），成交额和涨跌统计应正常写库。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 不含 breadth_quality 的旧格式数据
        await service.save_market_data(trade_date, sample_data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        assert cached["volume"]["total_volume"] == 7000.0
        assert cached["statistics"]["up_count"] == 2000

    @pytest.mark.asyncio
    async def test_error_global_context_does_not_overwrite_ok(self, integration_db, sample_data):
        """error 海外市场上下文不应覆盖已有 ok 缓存。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次：写入 ok 海外上下文
        await service.save_market_data(trade_date, sample_data)
        cached = await service.get_cached(trade_date)
        assert cached["global_market_context"]["status"] == "ok"

        # 第二次：尝试写入 error 海外上下文
        error_data = {
            **sample_data,
            "global_market_context": {
                "status": "error",
                "target_a_trade_date": "2026-03-27",
                "message": "主源被拒绝访问",
                "source": "yahoo_quote",
                "source_attempts": [{"source": "yahoo_quote", "status": "error", "failure_type": "unauthorized", "message": "401"}],
                "degraded": False,
            },
        }
        await service.save_market_data(trade_date, error_data)

        # 验证：ok 未被覆盖
        cached = await service.get_cached(trade_date)
        assert cached["global_market_context"]["status"] == "ok"
        assert cached["global_market_context"]["us_market"]["indices"][0]["symbol"] == "DJIA"

    @pytest.mark.asyncio
    async def test_error_global_context_does_not_overwrite_partial(self, integration_db, sample_data):
        """error 海外市场上下文不应覆盖已有 partial 缓存。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次：写入 partial 海外上下文
        partial_data = {
            **sample_data,
            "global_market_context": {
                "status": "partial",
                "target_a_trade_date": "2026-03-27",
                "captured_at": "2026-03-27T22:30:00+08:00",
                "as_of": "2026-03-27T22:29:00+08:00",
                "session": "regular",
                "source": "yahoo_quote",
                "message": "部分缺失",
                "us_market": {
                    "status": "partial",
                    "session": "regular",
                    "as_of": "2026-03-27T22:29:00+08:00",
                    "indices": [
                        {"symbol": "DJIA", "name": "道琼斯", "price": 39000.0, "change_pct": 0.004},
                    ],
                    "risk_signals": {},
                    "leaders": [],
                    "source": "yahoo_quote",
                },
            },
        }
        await service.save_market_data(trade_date, partial_data)

        # 第二次：尝试写入 error
        error_data = {
            **sample_data,
            "global_market_context": {
                "status": "error",
                "target_a_trade_date": "2026-03-27",
                "message": "网络错误",
                "source": "yahoo_quote",
                "source_attempts": [{"source": "yahoo_quote", "status": "error", "failure_type": "network_error", "message": "timeout"}],
                "degraded": False,
            },
        }
        await service.save_market_data(trade_date, error_data)

        cached = await service.get_cached(trade_date)
        assert cached["global_market_context"]["status"] == "partial"

    @pytest.mark.asyncio
    async def test_ok_global_context_overwrites_error(self, integration_db, sample_data):
        """ok 海外市场上下文应覆盖已有 error 缓存。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        # 第一次：写入 error
        error_data = {
            **sample_data,
            "global_market_context": {
                "status": "error",
                "target_a_trade_date": "2026-03-27",
                "message": "不可用",
                "source": "yahoo_quote",
                "source_attempts": [],
                "degraded": False,
            },
        }
        await service.save_market_data(trade_date, error_data)

        # 第二次：写入 ok
        await service.save_market_data(trade_date, sample_data)

        cached = await service.get_cached(trade_date)
        assert cached["global_market_context"]["status"] == "ok"
        assert cached["global_market_context"]["us_market"]["indices"][0]["symbol"] == "DJIA"

    @pytest.mark.asyncio
    async def test_provenance_metadata_round_trip(self, integration_db, sample_data):
        """source_attempts 和 degraded 元数据应随缓存原样读回。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        context_with_provenance = {
            **sample_data["global_market_context"],
            "source": "yahoo_chart",
            "degraded": True,
            "source_attempts": [
                {"source": "yahoo_quote", "status": "error", "failure_type": "unauthorized", "message": "401 Unauthorized"},
                {"source": "yahoo_chart", "status": "ok", "failure_type": "none", "message": ""},
            ],
        }
        data = {**sample_data, "global_market_context": context_with_provenance}
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        ctx = cached["global_market_context"]
        assert ctx["status"] == "ok"
        assert ctx["source"] == "yahoo_chart"
        assert ctx["degraded"] is True
        assert len(ctx["source_attempts"]) == 2
        assert ctx["source_attempts"][0]["failure_type"] == "unauthorized"
        assert ctx["source_attempts"][1]["source"] == "yahoo_chart"

    @pytest.mark.asyncio
    async def test_mixed_breadth_quality_only_writes_ok_items(self, integration_db, sample_data):
        """volume=ok + statistics=error 时，仅成交额写库。"""
        service = MarketDataCacheService(integration_db)
        trade_date = date(2026, 3, 27)

        data = {
            **sample_data,
            "breadth_quality": {
                "volume": {"status": "ok", "source": "eastmoney_curl"},
                "statistics": {"status": "error", "source": "eastmoney_curl"},
            },
        }
        await service.save_market_data(trade_date, data)

        cached = await service.get_cached(trade_date)
        assert cached is not None
        # 成交额应写入
        assert cached["volume"]["total_volume"] == 7000.0
        # 涨跌统计不应写入
        assert cached["statistics"]["up_count"] == 0
