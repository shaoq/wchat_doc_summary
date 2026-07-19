"""TickFlow rate_limits 单测（不依赖 tickflow SDK / 网络）。"""

import pytest

from src.api.market_providers.tickflow import rate_limits as rl
from src.api.market_providers.tickflow.rate_limits import (
    _reserve_slot,
    chunked,
    sleep_between_batches,
)


@pytest.fixture(autouse=True)
def _clear_slots():
    """每个测试前清空共享时间轴，避免互相污染。"""
    rl.reset_slots()
    yield
    rl.reset_slots()


def test_chunked_basic():
    assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunked([1, 2], None) == [[1, 2]]
    assert chunked([], 100) == []


def test_reserve_slot_first_is_near_zero():
    """同 rpm 首次预约：几乎不等待。"""
    rpm = 60
    interval = 60.0 / rpm  # 1.0s
    wait = _reserve_slot(rpm, interval)
    assert wait < 0.05


def test_reserve_slot_queues_subsequent():
    """同 rpm 连续预约：后续请求排到前一个 + interval 之后。"""
    rpm = 60
    interval = 60.0 / rpm
    _reserve_slot(rpm, interval)
    wait2 = _reserve_slot(rpm, interval)
    # 第二次至少等 interval（扣除调用间微小耗时）
    assert wait2 >= interval - 0.1


def test_sleep_between_batches_first_no_sleep(monkeypatch):
    """首批 (index=0) 不 sleep，仅登记占位槽。"""
    sleeps: list[float] = []
    monkeypatch.setattr(rl.time, "sleep", lambda s: sleeps.append(s))
    sleep_between_batches(0, rpm=60)
    assert sleeps == []


def test_sleep_between_batches_later_batches_sleep(monkeypatch):
    """后续批次在共享时间轴上 sleep。"""
    sleeps: list[float] = []
    monkeypatch.setattr(rl.time, "sleep", lambda s: sleeps.append(s))
    sleep_between_batches(0, rpm=60)  # 首批登记
    sleep_between_batches(1, rpm=60)  # 第二批
    assert len(sleeps) == 1
    assert sleeps[0] >= 0  # 非负等待


def test_sleep_between_batches_no_rpm_noop(monkeypatch):
    """rpm=None/0 不限流。"""
    monkeypatch.setattr(rl.time, "sleep", lambda s: pytest.fail("不应 sleep"))
    sleep_between_batches(0, rpm=None)
    sleep_between_batches(5, rpm=0)
