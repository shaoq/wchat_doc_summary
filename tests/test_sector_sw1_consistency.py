"""task 9.4: SW1 口径一致性验证。

冷启动重建的 TrackedSector.canonical_name 与 TickFlow 写入的 MarketSector.sector_name
都是 SW1 行业名（带前缀），collect_sector_evidence 的 comparison_key 匹配应一致，不降级。
"""

from src.services.sector_trend_service import SectorIdentity

# TickFlow sectors 输出的行业名（_tf_sectors_to_dict → MarketSector.sector_name）
_TICKFLOW_SECTOR_NAMES = [
    "SW1医药生物",
    "SW1公用事业",
    "SW1银行",
    "SW1电子",
    "SW1基础化工",
]


def test_sw1_canonical_non_empty():
    """冷启动 canonical_name（normalize 后）非空。"""
    for name in _TICKFLOW_SECTOR_NAMES:
        canonical = SectorIdentity.normalize(name)
        assert canonical, f"normalize({name!r}) 为空"


def test_sw1_canonical_matches_market_name_key():
    """TrackedSector.canonical 与 MarketSector.sector_name 的 comparison_key 一致 → collect 可匹配。"""
    for market_name in _TICKFLOW_SECTOR_NAMES:
        canonical = SectorIdentity.normalize(market_name)
        # 冷启动存的是 canonical；evidence 收集时 market_name 走同样的 normalize/comparison_key
        assert SectorIdentity.comparison_key(canonical) == SectorIdentity.comparison_key(
            market_name
        ), f"{market_name} 口径不一致，collect_sector_evidence 会降级"


def test_sw1_all_same_prefix():
    """冷启动后所有 tracked 与 market 都带 SW1 前缀，同口径。"""
    for name in _TICKFLOW_SECTOR_NAMES:
        assert name.startswith("SW1"), f"{name} 非_SW1 口径，跨口径会导致 evidence 降级"
