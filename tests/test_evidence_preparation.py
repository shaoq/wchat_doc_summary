"""证据准备服务单元测试 — 准备结果合并、置信度行为、来源和诊断聚合。"""

import pytest

from src.services.evidence_preparation import (
    EntityType,
    EvidenceRole,
    ConfidenceTier,
    MarketEvidenceRoleResult,
    PreparationDiagnostics,
    PreparationProvenance,
    SectorPreparationResult,
    GroupPreparationResult,
    classify_confidence_tier,
    can_satisfy_trend_gate,
    merge_preparation_results,
)


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

def _make_sector_result(
    sector_name: str = "机器人",
    market_role: EvidenceRole = EvidenceRole.NO_MARKET,
    confidence: ConfidenceTier = ConfidenceTier.LOW,
    aliases: list[str] | None = None,
    proxy_count: int = 0,
    watch_count: int = 0,
) -> SectorPreparationResult:
    """构建测试用板块准备结果。"""
    diag = PreparationDiagnostics(
        entity_type=EntityType.SECTOR,
        entity_name=sector_name,
        target_date="2026-05-14",
        window_days=10,
        repaired_watch_count=watch_count,
    )
    role_details: list[MarketEvidenceRoleResult] = []
    if market_role != EvidenceRole.NO_MARKET:
        role_details.append(MarketEvidenceRoleResult(
            role=market_role,
            sector_name=sector_name,
            confidence=confidence,
            provenance=PreparationProvenance(
                source="market_cache",
                matched_term=sector_name,
                confidence=confidence,
            ),
        ))

    proxies = [
        {"sector_name": f"proxy_{i}", "confidence": "medium"}
        for i in range(proxy_count)
    ]

    return SectorPreparationResult(
        sector_name=sector_name,
        target_date="2026-05-14",
        window_days=10,
        confidence_tier=confidence,
        diagnostics=diag,
        market_role=market_role,
        market_role_details=role_details,
        high_confidence_aliases=aliases or [],
        proxy_candidates=proxies,
    )


# ---------------------------------------------------------------------------
# 置信度分类
# ---------------------------------------------------------------------------

class TestClassifyConfidenceTier:
    """classify_confidence_tier 测试。"""

    def test_exact_market_is_high(self) -> None:
        result = _make_sector_result(market_role=EvidenceRole.EXACT_MARKET, confidence=ConfidenceTier.HIGH)
        assert classify_confidence_tier(result) == ConfidenceTier.HIGH

    def test_high_alias_with_watch_is_high(self) -> None:
        result = _make_sector_result(
            market_role=EvidenceRole.ALIAS_MARKET,
            confidence=ConfidenceTier.HIGH,
            watch_count=5,
        )
        assert classify_confidence_tier(result) == ConfidenceTier.HIGH

    def test_high_alias_without_watch_is_medium(self) -> None:
        result = _make_sector_result(
            market_role=EvidenceRole.ALIAS_MARKET,
            confidence=ConfidenceTier.HIGH,
            watch_count=0,
        )
        assert classify_confidence_tier(result) == ConfidenceTier.MEDIUM

    def test_proxy_market_is_medium(self) -> None:
        result = _make_sector_result(
            market_role=EvidenceRole.PROXY_MARKET,
            confidence=ConfidenceTier.MEDIUM,
        )
        assert classify_confidence_tier(result) == ConfidenceTier.MEDIUM

    def test_no_market_is_low(self) -> None:
        result = _make_sector_result(market_role=EvidenceRole.NO_MARKET)
        assert classify_confidence_tier(result) == ConfidenceTier.LOW


# ---------------------------------------------------------------------------
# 趋势门控
# ---------------------------------------------------------------------------

class TestCanSatisfyTrendGate:
    """can_satisfy_trend_gate 测试。"""

    def test_high_confidence_satisfies(self) -> None:
        result = _make_sector_result(confidence=ConfidenceTier.HIGH)
        assert can_satisfy_trend_gate(result) is True

    def test_medium_confidence_satisfies(self) -> None:
        result = _make_sector_result(confidence=ConfidenceTier.MEDIUM)
        assert can_satisfy_trend_gate(result) is True

    def test_low_confidence_does_not_satisfy(self) -> None:
        result = _make_sector_result(confidence=ConfidenceTier.LOW)
        assert can_satisfy_trend_gate(result) is False


# ---------------------------------------------------------------------------
# 准备结果合并
# ---------------------------------------------------------------------------

class TestMergePreparationResults:
    """merge_preparation_results 测试。"""

    def test_merge_takes_higher_confidence(self) -> None:
        low = _make_sector_result(sector_name="机器人", confidence=ConfidenceTier.LOW)
        high = _make_sector_result(sector_name="机器人", confidence=ConfidenceTier.HIGH)
        merged = merge_preparation_results(low, high)
        assert merged.confidence_tier == ConfidenceTier.HIGH

    def test_merge_aliases_deduplicates(self) -> None:
        a = _make_sector_result(aliases=["alias_a", "alias_b"])
        b = _make_sector_result(aliases=["alias_b", "alias_c"])
        merged = merge_preparation_results(a, b)
        assert set(merged.high_confidence_aliases) == {"alias_a", "alias_b", "alias_c"}

    def test_merge_market_role_takes_better(self) -> None:
        proxy = _make_sector_result(market_role=EvidenceRole.PROXY_MARKET, confidence=ConfidenceTier.MEDIUM)
        exact = _make_sector_result(market_role=EvidenceRole.EXACT_MARKET, confidence=ConfidenceTier.HIGH)
        merged = merge_preparation_results(proxy, exact)
        assert merged.market_role == EvidenceRole.EXACT_MARKET

    def test_merge_proxies_deduplicates_by_name(self) -> None:
        a = _make_sector_result(proxy_count=2)
        # 手动设置不同的 proxy 名称
        b = _make_sector_result()
        b.proxy_candidates = [
            {"sector_name": "other_proxy_0", "confidence": "medium"},
            {"sector_name": "other_proxy_1", "confidence": "medium"},
        ]
        merged = merge_preparation_results(a, b)
        # proxy_0, proxy_1 from a + other_proxy_0, other_proxy_1 from b
        proxy_names = {p["sector_name"] for p in merged.proxy_candidates}
        assert len(proxy_names) == 4

    def test_merge_diagnostics_aggregates(self) -> None:
        a = _make_sector_result(watch_count=3)
        b = _make_sector_result(watch_count=5)
        merged = merge_preparation_results(a, b)
        assert merged.diagnostics.repaired_watch_count == 5  # max

    def test_merge_skipped_matches_combined(self) -> None:
        a = _make_sector_result()
        b = _make_sector_result()
        a.diagnostics.skipped_matches = [{"term": "x", "reason": "noise"}]
        b.diagnostics.skipped_matches = [{"term": "y", "reason": "disabled"}]
        merged = merge_preparation_results(a, b)
        assert len(merged.diagnostics.skipped_matches) == 2

    def test_merge_market_role_details_deduplicates(self) -> None:
        a = _make_sector_result(market_role=EvidenceRole.EXACT_MARKET, confidence=ConfidenceTier.HIGH)
        b = _make_sector_result(market_role=EvidenceRole.ALIAS_MARKET, confidence=ConfidenceTier.HIGH)
        # b 使用不同 sector_name
        b.market_role_details = [MarketEvidenceRoleResult(
            role=EvidenceRole.ALIAS_MARKET,
            sector_name="机器人概念",
            confidence=ConfidenceTier.HIGH,
        )]
        merged = merge_preparation_results(a, b)
        assert len(merged.market_role_details) == 2


# ---------------------------------------------------------------------------
# 诊断序列化
# ---------------------------------------------------------------------------

class TestDiagnosticsSerialization:
    """PreparationDiagnostics.to_dict 测试。"""

    def test_to_dict_has_required_fields(self) -> None:
        diag = PreparationDiagnostics(
            entity_type=EntityType.SECTOR,
            entity_name="机器人",
            target_date="2026-05-14",
            window_days=10,
            repaired_watch_count=5,
        )
        d = diag.to_dict()
        assert d["entity_type"] == "sector"
        assert d["entity_name"] == "机器人"
        assert d["repaired_watch_count"] == 5
        assert "skipped_matches" in d
        assert "low_confidence_ignored" in d


class TestSectorPreparationResultSerialization:
    """SectorPreparationResult.to_dict 测试。"""

    def test_to_dict_has_required_fields(self) -> None:
        result = _make_sector_result()
        d = result.to_dict()
        assert d["sector_name"] == "机器人"
        assert d["confidence_tier"] == "low"
        assert d["market_role"] == "no_market"
        assert "diagnostics" in d
        assert "high_confidence_aliases" in d
        assert "proxy_candidates" in d

    def test_to_dict_market_role_details_serialized(self) -> None:
        result = _make_sector_result(
            market_role=EvidenceRole.EXACT_MARKET,
            confidence=ConfidenceTier.HIGH,
        )
        d = result.to_dict()
        assert len(d["market_role_details"]) == 1
        assert d["market_role_details"][0]["role"] == "exact_market"
        assert d["market_role_details"][0]["provenance"]["source"] == "market_cache"


class TestGroupPreparationResultSerialization:
    """GroupPreparationResult.to_dict 测试。"""

    def test_to_dict_includes_member_results(self) -> None:
        group = GroupPreparationResult(
            group_name="人形机器人链",
            target_date="2026-05-14",
            window_days=10,
            total_members=2,
            fresh_active_members=1,
            proxy_backed_members=0,
            low_confidence_ignored=1,
            unresolved_gaps=["1_low_confidence_members"],
            member_results=[
                _make_sector_result(sector_name="机器人", confidence=ConfidenceTier.HIGH),
                _make_sector_result(sector_name="减速器", confidence=ConfidenceTier.LOW),
            ],
        )
        d = group.to_dict()
        assert d["group_name"] == "人形机器人链"
        assert d["total_members"] == 2
        assert d["fresh_active_members"] == 1
        assert len(d["member_results"]) == 2
        assert "unresolved_gaps" in d


# ---------------------------------------------------------------------------
# 枚举值
# ---------------------------------------------------------------------------

class TestEnums:
    """枚举值验证。"""

    def test_evidence_roles(self) -> None:
        assert EvidenceRole.EXACT_MARKET.value == "exact_market"
        assert EvidenceRole.ALIAS_MARKET.value == "alias_market"
        assert EvidenceRole.PROXY_MARKET.value == "proxy_market"
        assert EvidenceRole.NO_MARKET.value == "no_market"

    def test_confidence_tiers(self) -> None:
        assert ConfidenceTier.HIGH.value == "high"
        assert ConfidenceTier.MEDIUM.value == "medium"
        assert ConfidenceTier.LOW.value == "low"

    def test_entity_types(self) -> None:
        assert EntityType.SECTOR.value == "sector"
        assert EntityType.GROUP.value == "group"
