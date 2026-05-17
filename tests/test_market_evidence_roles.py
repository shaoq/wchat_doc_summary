"""市场证据角色分类测试 — exact, alias, proxy, no-market 和混合角色。"""

import pytest

from src.services.evidence_preparation import (
    ConfidenceTier,
    EvidenceRole,
    MarketEvidenceRoleResult,
    PreparationDiagnostics,
    PreparationProvenance,
    SectorPreparationResult,
    EntityType,
)


class TestExactMarketEvidence:
    """exact_market 角色测试。"""

    def test_exact_match_from_canonical_identity(self) -> None:
        role = MarketEvidenceRoleResult(
            role=EvidenceRole.EXACT_MARKET,
            sector_name="机器人",
            confidence=ConfidenceTier.HIGH,
            provenance=PreparationProvenance(
                source="market_cache",
                matched_term="机器人",
                confidence=ConfidenceTier.HIGH,
                detail="canonical identity match",
            ),
        )
        assert role.role == EvidenceRole.EXACT_MARKET
        assert role.confidence == ConfidenceTier.HIGH
        assert role.provenance.source == "market_cache"


class TestAliasMarketEvidence:
    """alias_market 角色测试。"""

    def test_alias_from_explicit_alias(self) -> None:
        role = MarketEvidenceRoleResult(
            role=EvidenceRole.ALIAS_MARKET,
            sector_name="机器人概念",
            confidence=ConfidenceTier.HIGH,
            provenance=PreparationProvenance(
                source="alias",
                matched_term="机器人概念",
                confidence=ConfidenceTier.HIGH,
                detail="explicit alias match",
            ),
        )
        assert role.role == EvidenceRole.ALIAS_MARKET
        assert role.confidence == ConfidenceTier.HIGH

    def test_alias_from_accepted_equivalent(self) -> None:
        role = MarketEvidenceRoleResult(
            role=EvidenceRole.ALIAS_MARKET,
            sector_name="人形机器人",
            confidence=ConfidenceTier.HIGH,
            provenance=PreparationProvenance(
                source="learned_term",
                matched_term="人形机器人",
                confidence=ConfidenceTier.HIGH,
                detail="accepted equivalent identity",
            ),
        )
        assert role.role == EvidenceRole.ALIAS_MARKET


class TestProxyMarketEvidence:
    """proxy_market 角色测试。"""

    def test_proxy_from_theme_member(self) -> None:
        role = MarketEvidenceRoleResult(
            role=EvidenceRole.PROXY_MARKET,
            sector_name="减速器",
            confidence=ConfidenceTier.MEDIUM,
            provenance=PreparationProvenance(
                source="theme_member",
                matched_term="减速器",
                confidence=ConfidenceTier.MEDIUM,
                detail="member of theme '人形机器人链'",
            ),
        )
        assert role.role == EvidenceRole.PROXY_MARKET
        assert role.confidence == ConfidenceTier.MEDIUM

    def test_proxy_from_group_member(self) -> None:
        role = MarketEvidenceRoleResult(
            role=EvidenceRole.PROXY_MARKET,
            sector_name="伺服电机",
            confidence=ConfidenceTier.MEDIUM,
            provenance=PreparationProvenance(
                source="group_member",
                matched_term="伺服电机",
                confidence=ConfidenceTier.MEDIUM,
                detail="same group member",
            ),
        )
        assert role.role == EvidenceRole.PROXY_MARKET


class TestNoMarketEvidence:
    """no_market 角色测试。"""

    def test_no_market_is_default(self) -> None:
        result = SectorPreparationResult(
            sector_name="新板块",
            target_date="2026-05-14",
            window_days=10,
        )
        assert result.market_role == EvidenceRole.NO_MARKET
        assert result.confidence_tier == ConfidenceTier.LOW

    def test_no_market_with_only_low_confidence(self) -> None:
        """低置信度匹配结果仍为 no_market。"""
        result = SectorPreparationResult(
            sector_name="未知板块",
            target_date="2026-05-14",
            window_days=10,
            market_role=EvidenceRole.NO_MARKET,
            confidence_tier=ConfidenceTier.LOW,
        )
        assert result.market_role == EvidenceRole.NO_MARKET


class TestMixedRoleEvidence:
    """混合角色证据测试。"""

    def test_multiple_roles_in_result(self) -> None:
        """一个板块可以同时有 exact 和 proxy 证据。"""
        result = SectorPreparationResult(
            sector_name="机器人",
            target_date="2026-05-14",
            window_days=10,
            market_role=EvidenceRole.EXACT_MARKET,
            confidence_tier=ConfidenceTier.HIGH,
            market_role_details=[
                MarketEvidenceRoleResult(
                    role=EvidenceRole.EXACT_MARKET,
                    sector_name="机器人",
                    confidence=ConfidenceTier.HIGH,
                ),
                MarketEvidenceRoleResult(
                    role=EvidenceRole.PROXY_MARKET,
                    sector_name="减速器",
                    confidence=ConfidenceTier.MEDIUM,
                ),
            ],
        )
        roles = [r.role for r in result.market_role_details]
        assert EvidenceRole.EXACT_MARKET in roles
        assert EvidenceRole.PROXY_MARKET in roles
        assert result.market_role == EvidenceRole.EXACT_MARKET

    def test_role_priority_exact_over_proxy(self) -> None:
        """exact 市场角色优先于 proxy。"""
        role_priority = {
            EvidenceRole.EXACT_MARKET: 4,
            EvidenceRole.ALIAS_MARKET: 3,
            EvidenceRole.PROXY_MARKET: 2,
            EvidenceRole.NO_MARKET: 1,
        }
        roles = [EvidenceRole.PROXY_MARKET, EvidenceRole.EXACT_MARKET]
        best = max(roles, key=lambda r: role_priority.get(r, 0))
        assert best == EvidenceRole.EXACT_MARKET

    def test_role_priority_alias_over_proxy(self) -> None:
        """alias 市场角色优先于 proxy。"""
        role_priority = {
            EvidenceRole.EXACT_MARKET: 4,
            EvidenceRole.ALIAS_MARKET: 3,
            EvidenceRole.PROXY_MARKET: 2,
            EvidenceRole.NO_MARKET: 1,
        }
        roles = [EvidenceRole.PROXY_MARKET, EvidenceRole.ALIAS_MARKET]
        best = max(roles, key=lambda r: role_priority.get(r, 0))
        assert best == EvidenceRole.ALIAS_MARKET


class TestProxyIdentityBoundary:
    """代理证据不合并板块身份。"""

    def test_proxy_does_not_change_sector_name(self) -> None:
        """代理候选不会改变目标板块名称。"""
        result = SectorPreparationResult(
            sector_name="机器人",
            target_date="2026-05-14",
            window_days=10,
            proxy_candidates=[
                {"sector_name": "减速器", "confidence": "medium"},
            ],
        )
        # 代理候选和主体板块名称独立
        assert result.sector_name == "机器人"
        assert result.proxy_candidates[0]["sector_name"] == "减速器"

    def test_proxy_not_in_high_confidence_aliases(self) -> None:
        """代理候选不属于高置信度别名。"""
        result = SectorPreparationResult(
            sector_name="机器人",
            target_date="2026-05-14",
            window_days=10,
            high_confidence_aliases=["机器人概念"],
            proxy_candidates=[
                {"sector_name": "减速器", "confidence": "medium"},
            ],
        )
        assert "减速器" not in result.high_confidence_aliases
        assert "机器人概念" in result.high_confidence_aliases
