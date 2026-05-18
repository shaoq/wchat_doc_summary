#!/usr/bin/env python3
"""板块趋势矩阵历史回补脚本。

根据当前日期自动计算最近 N 个交易日，逐日调用 update_all_sector_trends
补齐 SectorTrendSummary 记录，使趋势矩阵显示完整历史。

用法:
    # 补齐最近 10 个交易日（默认）
    python scripts/backfill_sector_trends.py

    # 补齐最近 20 个交易日
    python scripts/backfill_sector_trends.py --days 20

    # 试运行（只打印要补齐的日期，不实际执行）
    python scripts/backfill_sector_trends.py --dry-run

    # 跳过证据准备（加速）
    python scripts/backfill_sector_trends.py --skip-preparation
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# 确保 src 目录可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.trade_calendar import is_trade_day
from src.storage.database import get_db


def resolve_recent_trade_dates(count: int = 10) -> list[date]:
    """从今天往前回溯，找到最近 count 个交易日（升序排列）。"""
    today = date.today()
    dates: list[date] = []
    check = today

    for _ in range(count * 3):  # 多找一些确保够
        check -= timedelta(days=1)
        if is_trade_day(check):
            dates.append(check)
        if len(dates) >= count:
            break

    dates.reverse()  # 升序：从最早到最近
    return dates


async def run_backfill(
    trade_dates: list[date],
    *,
    skip_preparation: bool = False,
    dry_run: bool = False,
) -> None:
    """逐日执行批量板块趋势更新。"""
    from src.services.ai_processor import AIProcessor
    from src.services.sector_trend_service import SectorTrendAnalyzer, SectorUpdateProgressEvent

    if dry_run:
        print(f"[试运行] 需要补齐 {len(trade_dates)} 个交易日:")
        for d in trade_dates:
            weekday_cn = "一二三四五六日"[d.weekday()]
            print(f"  {d} (周{weekday_cn})")
        return

    db = await get_db()
    analyzer = SectorTrendAnalyzer(db)

    try:
        ai_processor = AIProcessor(db)
    except ValueError as e:
        print(f"AI 初始化失败: {e}")
        return

    total = len(trade_dates)

    for idx, target_date in enumerate(trade_dates, 1):
        print(f"\n{'='*50}")
        print(f"[{idx}/{total}] 补齐交易日: {target_date}")
        print(f"{'='*50}")

        def _on_progress(event: SectorUpdateProgressEvent) -> None:
            if event.type == "batch_start":
                print(f"  目标: {event.target_count} 个板块")
            elif event.type == "sector_done":
                labels = event.labels
                label_text = " ".join(
                    v for v in [
                        labels.get("trend_status", ""),
                        labels.get("strength_level", ""),
                        labels.get("action_bias", ""),
                    ] if v
                )
                print(f"  [{event.sector_index}/{event.sector_total}] "
                      f"{event.sector_name}: {event.action} {label_text}")
            elif event.type == "sector_skipped":
                print(f"  [{event.sector_index}/{event.sector_total}] "
                      f"{event.sector_name}: 跳过")
            elif event.type == "sector_failed":
                print(f"  [{event.sector_index}/{event.sector_total}] "
                      f"{event.sector_name}: 失败 - {event.error[:60]}")
            elif event.type == "batch_done":
                print(f"  汇总: 成功={event.success_count} "
                      f"跳过={event.skipped_count} 失败={event.failed_count}")

        result = await analyzer.update_all_sector_trends(
            ai_processor=ai_processor,
            report_date=target_date,
            force=False,
            skip_repair=True,
            skip_preparation=skip_preparation,
            continue_on_error=True,
            progress_callback=_on_progress,
        )

    print(f"\n{'='*50}")
    print(f"回补完成: 共处理 {total} 个交易日")
    print(f"{'='*50}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="板块趋势矩阵历史回补",
    )
    parser.add_argument(
        "--days", type=int, default=10,
        help="补齐最近 N 个交易日（默认 10）",
    )
    parser.add_argument(
        "--skip-preparation", action="store_true",
        help="跳过证据准备（加速）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印要补齐的日期，不实际执行",
    )
    args = parser.parse_args()

    trade_dates = resolve_recent_trade_dates(args.days)

    if not trade_dates:
        print("未找到交易日")
        return

    print(f"补齐范围: {trade_dates[0]} ~ {trade_dates[-1]} ({len(trade_dates)} 个交易日)")

    asyncio.run(run_backfill(
        trade_dates,
        skip_preparation=args.skip_preparation,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
