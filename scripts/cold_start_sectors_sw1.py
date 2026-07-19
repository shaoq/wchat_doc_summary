"""板块 SW1 冷启动：归档旧东财概念数据 + 清空板块表 + 按 SW1 重建 tracked_sectors。

破坏性但归档保留（output/sector_trends, output/sector_groups → output/archive/<name>_<date>）。
重建 tracked_sectors 从 industry_members 的 unique SW1 行业名（每名取一个 representative code）。

用法：python scripts/cold_start_sectors_sw1.py
前置：industry_members 已填充（mixed/tickflow 模式下 sectors 调用一次即预热）。
"""
from __future__ import annotations

import asyncio
import shutil
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select

from src.models.schema import (
    IndustryMember,
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    SectorGroupTrendSummary,
    SectorTrendSummary,
    TrackedSector,
)
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import get_db


async def main() -> None:
    db = await get_db()
    today = date.today().isoformat()

    # 1. 归档 output（移动，可恢复）
    for sub in ("sector_trends", "sector_groups"):
        src = Path("output") / sub
        if src.exists() and any(src.iterdir()):
            archive = Path("output/archive") / f"{sub}_{today}"
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(archive))
            print(f"归档 {src} -> {archive}")
        else:
            print(f"跳过 {src}（不存在或为空）")

    # 2. 清空板块相关表（注意外键顺序：先子后父）
    async with db.get_session() as session:
        for model in (
            SectorGroupSuggestionMember,
            SectorGroupSuggestion,
            SectorGroupTrendSummary,
            SectorGroupMember,
            SectorGroup,
            SectorTrendSummary,
            TrackedSector,
        ):
            result = await session.execute(delete(model))
            print(f"清空 {model.__tablename__}: {result.rowcount} 行")

    # 3. 按 industry_members 的 unique SW1 行业名重建 tracked_sectors
    async with db.get_session() as session:
        result = await session.execute(
            select(IndustryMember.industry_name, IndustryMember.industry_code)
            .group_by(IndustryMember.industry_name)
        )
        industries = result.all()

    created = 0
    skipped: list[str] = []
    async with db.get_session() as session:
        for name, code in industries:
            canonical = SectorIdentity.normalize(name)
            if not canonical:
                skipped.append(name)
                continue
            session.add(
                TrackedSector(
                    canonical_name=canonical,
                    sector_code=code,
                    category="industry",
                    status="tracked",
                    source="cold_start_sw1",
                    first_seen_date=date.today(),
                    last_seen_date=date.today(),
                    discovery_reason=f"SW1 冷启动重建 ({code})",
                )
            )
            created += 1
    print(f"按 SW1 重建 tracked_sectors: {created} 个 (unique 行业名)")
    if skipped:
        print(f"跳过 {len(skipped)} 个无法 normalize 的名: {skipped[:5]}")
    print("冷启动完成。后续趋势更新请用 `wchat ai sector-trends update`")


if __name__ == "__main__":
    asyncio.run(main())
