"""TickFlow 批量请求限流——进程级共享时间轴。

free 档 `kline.daily.batch` = 60rpm × 100标的。多个调用方按同一时间轴排队，
使聚合发包间隔 >= 60/rpm，避免 429。

移植自 tickflow-stock-panel 的 rate_limits.py（精简，去 Polars）。
"""
from __future__ import annotations

import threading
import time
from typing import TypeVar

T = TypeVar("T")

# 按 rpm 分桶的「下一个可用时刻」表，Lock 守护
_slot_lock = threading.Lock()
_next_slot: dict[int, float] = {}


def _reserve_slot(rpm: int, interval: float) -> float:
    """在共享时间轴为一次请求预约发包槽，返回需等待秒数 (>=0)。

    interval = 60/rpm。now 早于该 rpm 桶的 next_slot 时排到 next_slot，否则排到 now；
    随后把该桶 next_slot 后移 interval。持锁仅做时间账目，不在锁内 sleep。
    """
    key = rpm if rpm and rpm > 0 else -1
    with _slot_lock:
        now = time.monotonic()
        scheduled = max(now, _next_slot.get(key, now))
        _next_slot[key] = scheduled + interval
        return scheduled - now


def reset_slots() -> None:
    """清空时间轴（测试用）。"""
    with _slot_lock:
        _next_slot.clear()


def chunked(items: list[T], batch_size: int | None) -> list[list[T]]:
    """按 batch_size 切分；None 表示整批一次。"""
    if batch_size is None:
        return [items]
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def sleep_between_batches(index: int, rpm: int | None) -> None:
    """首批不 sleep（仅登记占位槽）；后续每批按 60/rpm 间隔 sleep。

    保持「首批不 sleep、后续每批间隔 60/rpm」的单调用方观感，同时让并发调用方
    在同一时间轴排队。
    """
    if not rpm or rpm <= 0:
        return
    interval = 60.0 / rpm
    if index <= 0:
        # 首批登记占位槽，让后续/并发调用方在同一时间轴排队
        _reserve_slot(rpm, interval)
        return
    wait = _reserve_slot(rpm, interval)
    if wait > 0:
        time.sleep(wait)
