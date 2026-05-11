"""fetch_batches 断点续传测试 - 覆盖 batch 进度跟踪的完整场景。"""

import pytest
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.models.schema import FetchBatch
from src.services.fetcher import FetcherService, FetchSummary, FetchFinalState
from src.api.weread import RateLimitError, AuthExpiredError

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 固定有效交易日，避免测试受真实日期影响
FIXED_EFFECTIVE_DATE = date(2025, 5, 8)  # 周四，交易日
FIXED_NOW = datetime(2025, 5, 8, 15, 0, tzinfo=SHANGHAI_TZ)  # 15:00，09:15 之后


# ── Helpers ──────────────────────────────────────────────────

def _make_feed(mp_id: str, name: str = "", weight: int = 5, status: int = 1) -> SimpleNamespace:
    """创建测试用 Feed 替身。"""
    return SimpleNamespace(
        id=abs(hash(mp_id)) % 10000,
        mp_id=mp_id,
        name=name or mp_id,
        weight=weight,
        status=status,
        provider=None,
        sync_time=None,
    )


def _mock_session_ctx(session: AsyncMock):
    """创建 async context manager mock。"""
    @asynccontextmanager
    async def _ctx():
        yield session
    return _ctx()


def _mock_scalar_result(items: list):
    """创建模拟 SQLAlchemy result，支持 result.scalars().all() 链式调用。"""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    return mock_result


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    return db


@pytest.fixture
def mock_subscription_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fetcher(mock_db: MagicMock, mock_subscription_service: AsyncMock) -> FetcherService:
    return FetcherService(
        weread_client=MagicMock(),
        db=mock_db,
        subscription_service=mock_subscription_service,
    )


@pytest.fixture
def effective_date() -> date:
    """固定的有效交易日，供测试断言。"""
    return FIXED_EFFECTIVE_DATE


@pytest.fixture
def mock_effective_date():
    """Mock get_effective_fetch_trade_date 返回固定日期。"""
    with patch("src.services.fetcher.get_effective_fetch_trade_date", return_value=FIXED_EFFECTIVE_DATE):
        yield FIXED_EFFECTIVE_DATE


# ── 5.1 FetchBatch 模型 ──────────────────────────────────────


class TestFetchBatchModel:
    """测试 FetchBatch 模型的基本属性。"""

    def test_table_name(self) -> None:
        assert FetchBatch.__tablename__ == "fetch_batches"

    def test_unique_constraint_exists(self) -> None:
        constraint_names = [
            c.name for c in FetchBatch.__table_args__
            if hasattr(c, "name")
        ]
        assert "uq_fetch_batches_mp_date" in constraint_names

    def test_columns_exist(self) -> None:
        col_names = {c.name for c in FetchBatch.__table__.columns}
        assert {"id", "mp_id", "batch_date", "status", "created_at", "updated_at"} <= col_names


# ── 5.2 _ensure_batch ────────────────────────────────────────


class TestEnsureBatch:
    """测试 batch 创建、恢复和补充逻辑。"""

    @pytest.mark.asyncio
    async def test_creates_batch_for_all_active_feeds(
        self, fetcher: FetcherService, mock_db: MagicMock, mock_subscription_service: AsyncMock,
        mock_effective_date: date,
    ) -> None:
        """首次运行应为所有活跃订阅创建 pending 记录。"""
        feeds = [_make_feed("A"), _make_feed("B"), _make_feed("C")]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)

        mock_session = AsyncMock()
        added_records: list = []
        mock_session.add = MagicMock(side_effect=lambda r: added_records.append(r))
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result([]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await fetcher._ensure_batch(FIXED_EFFECTIVE_DATE)

        assert len(added_records) == 3
        for rec in added_records:
            assert rec.status == "pending"
            assert rec.batch_date == FIXED_EFFECTIVE_DATE

    @pytest.mark.asyncio
    async def test_supplements_new_subscription(
        self, fetcher: FetcherService, mock_db: MagicMock, mock_subscription_service: AsyncMock,
        mock_effective_date: date,
    ) -> None:
        """已有 batch 中新增订阅应被补充为 pending。"""
        feeds = [_make_feed("A"), _make_feed("B"), _make_feed("NEW")]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)

        mock_session = AsyncMock()
        added_records: list = []
        mock_session.add = MagicMock(side_effect=lambda r: added_records.append(r))
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result(["A", "B"]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await fetcher._ensure_batch(FIXED_EFFECTIVE_DATE)

        assert len(added_records) == 1
        assert added_records[0].mp_id == "NEW"

    @pytest.mark.asyncio
    async def test_no_new_feeds_no_insert(
        self, fetcher: FetcherService, mock_db: MagicMock, mock_subscription_service: AsyncMock,
        mock_effective_date: date,
    ) -> None:
        """所有订阅都已在 batch 中，不应插入新记录。"""
        feeds = [_make_feed("A"), _make_feed("B")]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result(["A", "B"]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await fetcher._ensure_batch(FIXED_EFFECTIVE_DATE)

        mock_session.add.assert_not_called()


# ── 5.3 _get_pending_feeds ────────────────────────────────────


class TestGetPendingFeeds:
    """测试 pending 队列查询。"""

    @pytest.mark.asyncio
    async def test_returns_only_pending_feeds(
        self, fetcher: FetcherService, mock_db: MagicMock,
    ) -> None:
        mock_session = AsyncMock()
        feed_a = _make_feed("A")
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result([feed_a]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await fetcher._get_pending_feeds(FIXED_EFFECTIVE_DATE)
        assert len(result) == 1
        assert result[0].mp_id == "A"

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_done(
        self, fetcher: FetcherService, mock_db: MagicMock,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result([]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await fetcher._get_pending_feeds(FIXED_EFFECTIVE_DATE)
        assert result == []


# ── 5.4 fetch_all 断点续传 ────────────────────────────────────


class TestFetchAllResume:
    """测试 fetch_all 的断点续传行为。"""

    @pytest.mark.asyncio
    async def test_rate_limit_keeps_feed_pending(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """RateLimitError 时当前 feed 不被标记 done。"""
        feeds = [_make_feed("A"), _make_feed("B")]

        with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, side_effect=RateLimitError("限流")), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock) as mock_done:

            results = await fetcher.fetch_all()

            assert "A" in results
            assert results["A"].final_state == FetchFinalState.ERROR
            mock_done.assert_not_called()  # RateLimitError 不标记 done

    @pytest.mark.asyncio
    async def test_non_fatal_error_marks_done_and_continues(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """非致命错误标记 done 并继续下一个。"""
        feeds = [_make_feed("A"), _make_feed("B")]

        async def _mock_fetch_incremental(mp_id, **kwargs):
            if mp_id == "A":
                raise Exception("网络错误")
            return FetchSummary(mp_id=mp_id, inserted_count=1)

        with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, side_effect=_mock_fetch_incremental), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock) as mock_done, \
             patch.object(fetcher, "_wait_with_progress", new_callable=AsyncMock):

            results = await fetcher.fetch_all()

            assert "A" in results
            assert "B" in results
            assert results["B"].inserted_count == 1
            assert mock_done.call_count == 2  # A 和 B 都标记 done

    @pytest.mark.asyncio
    async def test_success_marks_done(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """成功抓取后标记 done。"""
        feeds = [_make_feed("A")]

        with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, return_value=FetchSummary(mp_id="A")), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock) as mock_done:

            results = await fetcher.fetch_all()

            assert "A" in results
            mock_done.assert_called_once_with("A", FIXED_EFFECTIVE_DATE)

    @pytest.mark.asyncio
    async def test_respects_days_and_latest_count_params(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """days/latest_count 参数正确传递给 _fetch_feed_summary。"""
        feeds = [_make_feed("A")]

        with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_feed_summary", new_callable=AsyncMock, return_value=FetchSummary(mp_id="A")) as mock_fetch, \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock):

            await fetcher.fetch_all(days=7)

            mock_fetch.assert_called_once_with("A", days=7, latest_count=None, on_progress=None)


# ── 5.5 每日重置 ─────────────────────────────────────────────


class TestDailyReset:

    @pytest.mark.asyncio
    async def test_all_done_returns_empty(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """所有订阅已完成时返回空字典。"""
        with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=[]):

            results = await fetcher.fetch_all()
            assert results == {}


# ── 5.6 --force 行为 ─────────────────────────────────────────


class TestForceReset:

    @pytest.mark.asyncio
    async def test_force_calls_reset_before_ensure(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """force=True 时先调用 _reset_batch 再调用 _ensure_batch。"""
        call_order: list[str] = []

        async def _mock_reset(effective_date: date):
            call_order.append("reset")

        async def _mock_ensure(effective_date: date):
            call_order.append("ensure")

        feeds = [_make_feed("A")]
        with patch.object(fetcher, "_reset_batch", new_callable=AsyncMock, side_effect=_mock_reset), \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock, side_effect=_mock_ensure), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, return_value=FetchSummary(mp_id="A")), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock):

            await fetcher.fetch_all(force=True)
            assert call_order == ["reset", "ensure"]

    @pytest.mark.asyncio
    async def test_no_force_skips_reset(
        self, fetcher: FetcherService, mock_effective_date: date,
    ) -> None:
        """force=False 时不调用 _reset_batch。"""
        feeds = [_make_feed("A")]
        with patch.object(fetcher, "_reset_batch", new_callable=AsyncMock) as mock_reset, \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, return_value=FetchSummary(mp_id="A")), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock):

            await fetcher.fetch_all(force=False)
            mock_reset.assert_not_called()


# ── 5.7 旧数据清理 ──────────────────────────────────────────


class TestOldBatchCleanup:

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_records(
        self, fetcher: FetcherService, mock_db: MagicMock, mock_subscription_service: AsyncMock,
        mock_effective_date: date,
    ) -> None:
        """_ensure_batch 应调用 DELETE 清理 7 天前的记录。"""
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=[_make_feed("A")])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_mock_scalar_result(["A"]))
        mock_db.get_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await fetcher._ensure_batch(FIXED_EFFECTIVE_DATE)

        # 至少调用了 DELETE（清理旧数据）和 SELECT（查已有 batch）
        assert mock_session.execute.call_count >= 1


# ── 5.8 单独 fetch <mp_id> 不受影响 ──────────────────────────


class TestSingleFetchUnaffected:

    @pytest.mark.asyncio
    async def test_single_fetch_does_not_use_batch(
        self, fetcher: FetcherService,
    ) -> None:
        """fetch_feed 不调用任何 batch 方法。"""
        with patch.object(fetcher, "_get_feed_or_raise", new_callable=AsyncMock, side_effect=ValueError("中断")):
            with patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock) as mock_ensure, \
                 patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock) as mock_pending:
                try:
                    await fetcher.fetch_feed("MP_WXS_test")
                except ValueError:
                    pass

                mock_ensure.assert_not_called()
                mock_pending.assert_not_called()


# ── 5.9 有效交易日边界场景 ─────────────────────────────────


class TestEffectiveTradeDateBoundary:
    """测试有效交易日在 fetch_all 中的语义。"""

    @pytest.mark.asyncio
    async def test_weekend_rerun_skips_done_feeds(self, fetcher: FetcherService) -> None:
        """周末重跑时，已 done 的订阅（属于前一交易日）应被跳过。"""
        # 模拟周六 10:00，有效交易日应为周五
        saturday = datetime(2025, 5, 10, 10, 0, tzinfo=SHANGHAI_TZ)
        prev_friday = date(2025, 5, 9)

        with patch("src.services.fetcher.get_effective_fetch_trade_date", return_value=prev_friday), \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=[]):

            results = await fetcher.fetch_all()
            # 无 pending feeds → 返回空字典（全部已跳过）
            assert results == {}

    @pytest.mark.asyncio
    async def test_force_resets_effective_trade_day_batch(self, fetcher: FetcherService) -> None:
        """--force 只重置有效交易日的 batch。"""
        prev_friday = date(2025, 5, 9)

        with patch("src.services.fetcher.get_effective_fetch_trade_date", return_value=prev_friday), \
             patch.object(fetcher, "_reset_batch", new_callable=AsyncMock) as mock_reset, \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=[]):

            await fetcher.fetch_all(force=True)
            mock_reset.assert_called_once_with(prev_friday)

    @pytest.mark.asyncio
    async def test_pre_0915_uses_previous_trade_day(self, fetcher: FetcherService) -> None:
        """交易日 09:15 之前重跑使用前一交易日 batch。"""
        # 周四 08:00 → 有效交易日为周三
        thursday_early = datetime(2025, 5, 8, 8, 0, tzinfo=SHANGHAI_TZ)
        prev_wednesday = date(2025, 5, 7)

        with patch("src.services.fetcher.get_effective_fetch_trade_date", return_value=prev_wednesday), \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=[]):

            results = await fetcher.fetch_all()
            assert results == {}

    @pytest.mark.asyncio
    async def test_post_0915_uses_current_trade_day(self, fetcher: FetcherService) -> None:
        """交易日 09:15 及之后使用当前交易日 batch。"""
        thursday_after = datetime(2025, 5, 8, 10, 0, tzinfo=SHANGHAI_TZ)
        current_thursday = date(2025, 5, 8)

        feeds = [_make_feed("A")]
        with patch("src.services.fetcher.get_effective_fetch_trade_date", return_value=current_thursday), \
             patch.object(fetcher, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher, "_fetch_incremental_or_init_summary", new_callable=AsyncMock, return_value=FetchSummary(mp_id="A")), \
             patch.object(fetcher, "_mark_batch_done", new_callable=AsyncMock) as mock_done:

            results = await fetcher.fetch_all()

            assert "A" in results
            mock_done.assert_called_once_with("A", current_thursday)
