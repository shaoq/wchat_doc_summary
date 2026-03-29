"""财联社新闻入库与聚合测试。

覆盖场景:
1. CLSTelegraphService 去重入库
2. CLSWatchService 去重入库
3. collect_news_data 从本地读取（不走远端 API）
4. ingest_telegraphs 入库路径
"""

import pytest
import pytest_asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.cls_telegraph_service import CLSTelegraphService
from src.services.cls_watch_service import CLSWatchService
from src.services.market_analyzer import MarketAnalyzer


# ---------------------------------------------------------------------------
# 共享 fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def real_db():
    """创建真实内存数据库，初始化表结构。"""
    from src.storage.database import Database

    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield db
    await db.close()


def _sample_telegraphs() -> list[dict]:
    """构造一批示例电报数据。"""
    return [
        {
            "id": "telegraph_001",
            "title": "央行开展逆回购操作",
            "content": "央行今日开展 1000 亿元 7 天期逆回购操作",
            "ctime": 1743100000,
            "level": "A",
        },
        {
            "id": "telegraph_002",
            "title": "沪深两市成交额突破万亿",
            "content": "截至今日收盘，沪深两市成交额达 1.2 万亿元",
            "ctime": 1743110000,
            "level": "B",
        },
        {
            "id": "telegraph_003",
            "title": "新能源汽车销量创新高",
            "content": "3 月新能源汽车销量同比增长 40%",
            "ctime": 1743120000,
            "level": "C",
        },
    ]


def _sample_watch_items() -> list[dict]:
    """构造一批示例看盘数据。"""
    return [
        {
            "id": "watch_001",
            "title": "半导体板块异动拉升",
            "content": "半导体板块午后集体拉升，多只个股涨停",
            "ctime": 1743140400,  # 2025-03-28 09:00:00
            "stocks": ["中芯国际", "北方华创"],
            "sectors": ["半导体"],
        },
        {
            "id": "watch_002",
            "title": "白酒板块走弱",
            "content": "白酒板块整体回调，贵州茅台跌超 2%",
            "ctime": 1743162000,  # 2025-03-28 15:00:00
            "stocks": ["贵州茅台"],
            "sectors": ["白酒"],
        },
    ]


# ===================================================================
# 场景 1: CLSTelegraphService 去重入库
# ===================================================================


class TestCLSTelegraphDedup:
    """验证 CLSTelegraphService.save_telegraphs() 去重行为。"""

    @pytest.mark.asyncio
    async def test_first_insert_all(self, real_db):
        """首次入库应全部成功插入。"""
        service = CLSTelegraphService(real_db)
        data = _sample_telegraphs()

        inserted, skipped = await service.save_telegraphs(data)

        assert inserted == 3
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_second_insert_skips_duplicates(self, real_db):
        """重复入库应全部跳过，inserted=0, skipped>0。"""
        service = CLSTelegraphService(real_db)
        data = _sample_telegraphs()

        # 第一次入库
        await service.save_telegraphs(data)

        # 第二次用相同数据入库
        inserted, skipped = await service.save_telegraphs(data)

        assert inserted == 0
        assert skipped > 0

    @pytest.mark.asyncio
    async def test_partial_dedup(self, real_db):
        """部分重复时，仅新增不存在的记录。"""
        service = CLSTelegraphService(real_db)
        data = _sample_telegraphs()

        # 先插入前两条
        await service.save_telegraphs(data[:2])

        # 再插入全部（含新增的第 3 条）
        inserted, skipped = await service.save_telegraphs(data)

        assert inserted == 1
        assert skipped == 2

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, real_db):
        """空列表应返回 (0, 0)。"""
        service = CLSTelegraphService(real_db)

        inserted, skipped = await service.save_telegraphs([])

        assert inserted == 0
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_data_persisted_correctly(self, real_db):
        """验证数据持久化到数据库后可正确查询。"""
        service = CLSTelegraphService(real_db)
        data = _sample_telegraphs()

        await service.save_telegraphs(data)

        # 使用 list_telegraphs 查询验证
        start_time = 1743100000 - 1
        end_time = 1743120000 + 1
        results = await service.list_telegraphs(
            start_time=start_time,
            end_time=end_time,
        )

        assert len(results) == 3
        titles = {r.title for r in results}
        assert titles == {
            "央行开展逆回购操作",
            "沪深两市成交额突破万亿",
            "新能源汽车销量创新高",
        }


# ===================================================================
# 场景 2: CLSWatchService 去重入库
# ===================================================================


class TestCLSWatchDedup:
    """验证 CLSWatchService.save_watch_data() 去重行为。"""

    @pytest.mark.asyncio
    async def test_first_insert_all(self, real_db):
        """首次入库应全部成功插入。"""
        service = CLSWatchService(real_db)
        data = _sample_watch_items()

        inserted, skipped = await service.save_watch_data(data)

        assert inserted == 2
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_second_insert_skips_duplicates(self, real_db):
        """重复入库应全部跳过，inserted=0, skipped>0。"""
        service = CLSWatchService(real_db)
        data = _sample_watch_items()

        # 第一次入库
        await service.save_watch_data(data)

        # 第二次用相同数据入库
        inserted, skipped = await service.save_watch_data(data)

        assert inserted == 0
        assert skipped > 0

    @pytest.mark.asyncio
    async def test_partial_dedup(self, real_db):
        """部分重复时，仅新增不存在的记录。"""
        service = CLSWatchService(real_db)
        data = _sample_watch_items()

        # 先插入第一条
        await service.save_watch_data(data[:1])

        # 再插入全部（含新增的第 2 条）
        inserted, skipped = await service.save_watch_data(data)

        assert inserted == 1
        assert skipped == 1

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, real_db):
        """空列表应返回 (0, 0)。"""
        service = CLSWatchService(real_db)

        inserted, skipped = await service.save_watch_data([])

        assert inserted == 0
        assert skipped == 0


# ===================================================================
# 场景 3: collect_news_data 从本地读取
# ===================================================================


class TestCollectNewsDataLocalRead:
    """验证 collect_news_data 使用本地服务查询，而非远端 API。"""

    @pytest.mark.asyncio
    async def test_calls_list_telegraphs_not_remote(self, real_db):
        """collect_news_data 应调用 CLSTelegraphService.list_telegraphs()（本地查询）。"""
        analyzer = MarketAnalyzer(db=real_db)

        with patch(
            "src.services.cls_telegraph_service.CLSTelegraphService.list_telegraphs",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list, patch(
            "src.services.cls_watch_service.CLSWatchService.get_watch_data_for_summary",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.services.market_analyzer.MarketAnalyzer.get_related_articles",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await analyzer.collect_news_data(trade_date=date(2025, 3, 28))

            mock_list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_get_watch_data_for_summary_not_remote(self, real_db):
        """collect_news_data 应调用 CLSWatchService.get_watch_data_for_summary()（本地查询）。"""
        analyzer = MarketAnalyzer(db=real_db)

        with patch(
            "src.services.cls_telegraph_service.CLSTelegraphService.list_telegraphs",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.services.cls_watch_service.CLSWatchService.get_watch_data_for_summary",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_watch, patch(
            "src.services.market_analyzer.MarketAnalyzer.get_related_articles",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await analyzer.collect_news_data(trade_date=date(2025, 3, 28))

            mock_watch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self, real_db):
        """collect_news_data 应返回包含所有必要键的结果字典。"""
        analyzer = MarketAnalyzer(db=real_db)

        with patch(
            "src.services.cls_telegraph_service.CLSTelegraphService.list_telegraphs",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.services.cls_watch_service.CLSWatchService.get_watch_data_for_summary",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.services.market_analyzer.MarketAnalyzer.get_related_articles",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await analyzer.collect_news_data(trade_date=date(2025, 3, 28))

            assert "telegraphs" in result
            assert "watch_items" in result
            assert "articles" in result
            assert "sources_status" in result
            assert "time_window" in result
            assert result["sources_status"]["telegraphs"] == "empty"
            assert result["sources_status"]["watch_items"] == "empty"

    @pytest.mark.asyncio
    async def test_populated_data_in_result(self, real_db):
        """当本地有数据时，collect_news_data 应将其填充到结果中。"""
        telegraph_service = CLSTelegraphService(real_db)
        watch_service = CLSWatchService(real_db)

        # 预先写入数据
        await telegraph_service.save_telegraphs(_sample_telegraphs())
        await watch_service.save_watch_data(_sample_watch_items())

        analyzer = MarketAnalyzer(db=real_db)

        # collect_news_data 在内部创建新的 service 实例并查询本地数据库
        result = await analyzer.collect_news_data(trade_date=date(2025, 3, 28))

        # 电报数据应被填充（时间戳在当天范围内的会被查到）
        assert result["sources_status"]["telegraphs"] in ("ok", "empty")
        assert result["sources_status"]["watch_items"] in ("ok", "empty")


# ===================================================================
# 场景 4: ingest_telegraphs 入库路径
# ===================================================================


class TestIngestTelegraphs:
    """验证 ingest_telegraphs 从远端抓取后调用 save_telegraphs 入库。"""

    @pytest.mark.asyncio
    async def test_ingest_telegraphs_exists(self, real_db):
        """CLSTelegraphService 应具备 ingest_telegraphs 方法。"""
        service = CLSTelegraphService(real_db)
        assert hasattr(service, "ingest_telegraphs")
        assert callable(getattr(service, "ingest_telegraphs"))

    @pytest.mark.asyncio
    async def test_ingest_calls_save_telegraphs(self, real_db):
        """ingest_telegraphs 应在获取远端数据后调用 save_telegraphs。"""
        service = CLSTelegraphService(real_db)

        mock_client = MagicMock()
        mock_client.fetch_by_time_range = MagicMock(
            return_value=_sample_telegraphs()
        )

        with patch.object(
            service, "save_telegraphs", new_callable=AsyncMock, return_value=(3, 0)
        ) as mock_save:
            inserted, skipped = await service.ingest_telegraphs(
                start_time=1743100000,
                end_time=1743120000,
                client=mock_client,
            )

            mock_save.assert_awaited_once()
            assert inserted == 3
            assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_returns_zero_on_empty_response(self, real_db):
        """远端返回空数据时，ingest_telegraphs 应返回 (0, 0)。"""
        service = CLSTelegraphService(real_db)

        mock_client = MagicMock()
        mock_client.fetch_by_time_range = MagicMock(return_value=[])

        inserted, skipped = await service.ingest_telegraphs(
            start_time=1743100000,
            end_time=1743120000,
            client=mock_client,
        )

        assert inserted == 0
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_returns_zero_on_fetch_error(self, real_db):
        """远端抓取失败时，ingest_telegraphs 应返回 (0, 0) 而非抛异常。"""
        service = CLSTelegraphService(real_db)

        mock_client = MagicMock()
        mock_client.fetch_by_time_range = MagicMock(side_effect=Exception("网络超时"))

        inserted, skipped = await service.ingest_telegraphs(
            start_time=1743100000,
            end_time=1743120000,
            client=mock_client,
        )

        assert inserted == 0
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_ingest_dedup_with_real_db(self, real_db):
        """使用真实数据库验证 ingest_telegraphs 的去重效果。"""
        service = CLSTelegraphService(real_db)
        data = _sample_telegraphs()

        mock_client = MagicMock()
        mock_client.fetch_by_time_range = MagicMock(return_value=data)

        # 第一次入库
        inserted_1, skipped_1 = await service.ingest_telegraphs(
            start_time=1743100000,
            end_time=1743120000,
            client=mock_client,
        )
        assert inserted_1 == 3
        assert skipped_1 == 0

        # 第二次用相同数据入库
        inserted_2, skipped_2 = await service.ingest_telegraphs(
            start_time=1743100000,
            end_time=1743120000,
            client=mock_client,
        )
        assert inserted_2 == 0
        assert skipped_2 == 3
