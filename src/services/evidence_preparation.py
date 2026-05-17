"""板块证据准备服务 — 自动协调 CLS 看盘修复、板块身份信号、主题注册信号、
已接受学习词条和市场代理发现。

本服务在板块初始化、板块更新、分组成员变更和分组更新之前运行，
确保本地证据已准备就绪，用户无需手动执行修复或映射命令。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    AcceptedThemeTerm,
    CLSWatchData,
    MarketSector,
    SectorGroup,
    SectorGroupMember,
    ThemeTermSuggestion,
    TrackedSector,
)
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import Database

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 枚举与常量
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    """准备目标的实体类型。"""
    SECTOR = "sector"
    GROUP = "group"


class ConfidenceTier(str, Enum):
    """证据准备结果的置信度等级。"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceRole(str, Enum):
    """市场证据角色分类。"""
    EXACT_MARKET = "exact_market"
    ALIAS_MARKET = "alias_market"
    PROXY_MARKET = "proxy_market"
    NO_MARKET = "no_market"


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PreparationProvenance:
    """单条准备结果的来源信息。"""
    source: str  # "watch_repair" | "alias" | "theme" | "learned_term" | "group_member" | "market_proxy"
    matched_term: str
    confidence: ConfidenceTier
    detail: str = ""


@dataclass(frozen=True)
class MarketEvidenceRoleResult:
    """市场证据角色分类结果。"""
    role: EvidenceRole
    sector_name: str
    confidence: ConfidenceTier
    provenance: PreparationProvenance | None = None


@dataclass
class PreparationDiagnostics:
    """准备过程的诊断信息。"""
    entity_type: EntityType
    entity_name: str
    target_date: str  # ISO date
    window_days: int

    # 各来源的匹配计数
    repaired_watch_count: int = 0
    alias_matches: list[str] = field(default_factory=list)
    theme_matches: list[dict[str, str]] = field(default_factory=list)
    learned_term_matches: list[dict[str, str]] = field(default_factory=list)
    market_evidence_roles: list[dict[str, str]] = field(default_factory=list)
    proxy_candidates: list[dict[str, str]] = field(default_factory=list)

    # 跳过的匹配及原因
    skipped_matches: list[dict[str, str]] = field(default_factory=list)
    low_confidence_ignored: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "entity_type": self.entity_type.value,
            "entity_name": self.entity_name,
            "target_date": self.target_date,
            "window_days": self.window_days,
            "repaired_watch_count": self.repaired_watch_count,
            "alias_matches": self.alias_matches,
            "theme_matches": self.theme_matches,
            "learned_term_matches": self.learned_term_matches,
            "market_evidence_roles": self.market_evidence_roles,
            "proxy_candidates": self.proxy_candidates,
            "skipped_matches": self.skipped_matches,
            "low_confidence_ignored": self.low_confidence_ignored,
        }


@dataclass
class SectorPreparationResult:
    """单个板块的证据准备结果。"""
    sector_name: str
    target_date: str  # ISO date
    window_days: int
    confidence_tier: ConfidenceTier = ConfidenceTier.LOW
    diagnostics: PreparationDiagnostics = field(default_factory=lambda: PreparationDiagnostics(
        entity_type=EntityType.SECTOR, entity_name="", target_date="", window_days=0,
    ))

    # 市场证据角色
    market_role: EvidenceRole = EvidenceRole.NO_MARKET
    market_role_details: list[MarketEvidenceRoleResult] = field(default_factory=list)

    # 高置信度别名（可用于趋势验证）
    high_confidence_aliases: list[str] = field(default_factory=list)

    # 代理候选（不可用于直接趋势验证，仅用于诊断和连续性）
    proxy_candidates: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "sector_name": self.sector_name,
            "target_date": self.target_date,
            "window_days": self.window_days,
            "confidence_tier": self.confidence_tier.value,
            "market_role": self.market_role.value,
            "market_role_details": [
                {
                    "role": r.role.value,
                    "sector_name": r.sector_name,
                    "confidence": r.confidence.value,
                    "provenance": {
                        "source": r.provenance.source,
                        "matched_term": r.provenance.matched_term,
                        "confidence": r.provenance.confidence.value,
                        "detail": r.provenance.detail,
                    } if r.provenance else None,
                }
                for r in self.market_role_details
            ],
            "high_confidence_aliases": self.high_confidence_aliases,
            "proxy_candidates": self.proxy_candidates,
            "diagnostics": self.diagnostics.to_dict(),
        }


@dataclass
class GroupPreparationResult:
    """单个分组的证据准备结果。"""
    group_name: str
    target_date: str  # ISO date
    window_days: int
    member_results: list[SectorPreparationResult] = field(default_factory=list)
    diagnostics: PreparationDiagnostics = field(default_factory=lambda: PreparationDiagnostics(
        entity_type=EntityType.GROUP, entity_name="", target_date="", window_days=0,
    ))

    # 成员证据质量汇总
    total_members: int = 0
    fresh_active_members: int = 0
    proxy_backed_members: int = 0
    low_confidence_ignored: int = 0
    unresolved_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "group_name": self.group_name,
            "target_date": self.target_date,
            "window_days": self.window_days,
            "total_members": self.total_members,
            "fresh_active_members": self.fresh_active_members,
            "proxy_backed_members": self.proxy_backed_members,
            "low_confidence_ignored": self.low_confidence_ignored,
            "unresolved_gaps": self.unresolved_gaps,
            "member_results": [r.to_dict() for r in self.member_results],
            "diagnostics": self.diagnostics.to_dict(),
        }


# ---------------------------------------------------------------------------
# 置信度分类
# ---------------------------------------------------------------------------

def classify_confidence_tier(result: SectorPreparationResult) -> ConfidenceTier:
    """根据准备结果的证据质量分类置信度等级。

    - HIGH: 有 exact_market 或高置信度 alias_market 加上新 watch/telegraph 证据
    - MEDIUM: 有 proxy_market 或中置信度别名
    - LOW: 仅有低置信度匹配或无匹配

    Args:
        result: 板块准备结果

    Returns:
        置信度等级
    """
    roles = [r.role for r in result.market_role_details]

    has_exact = EvidenceRole.EXACT_MARKET in roles
    has_high_alias = any(
        r.role == EvidenceRole.ALIAS_MARKET and r.confidence == ConfidenceTier.HIGH
        for r in result.market_role_details
    )
    has_proxy = EvidenceRole.PROXY_MARKET in roles
    has_watch = result.diagnostics.repaired_watch_count > 0

    if has_exact:
        return ConfidenceTier.HIGH
    if has_high_alias and has_watch:
        return ConfidenceTier.HIGH
    if has_high_alias or has_proxy:
        return ConfidenceTier.MEDIUM
    return ConfidenceTier.LOW


def can_satisfy_trend_gate(result: SectorPreparationResult) -> bool:
    """判断准备结果是否能满足趋势提升门控。

    低置信度结果仅用于诊断，不能提升趋势阶段。

    Args:
        result: 板块准备结果

    Returns:
        True 如果结果可以参与趋势判定
    """
    return result.confidence_tier != ConfidenceTier.LOW


# ---------------------------------------------------------------------------
# 准备结果合并
# ---------------------------------------------------------------------------

def merge_preparation_results(
    base: SectorPreparationResult,
    additional: SectorPreparationResult,
) -> SectorPreparationResult:
    """合并两个准备结果，保留最高置信度和所有发现的证据。

    Args:
        base: 基础结果
        additional: 额外结果

    Returns:
        合并后的新结果（不可变模式）
    """
    # 合并市场角色详情
    merged_roles = list(base.market_role_details)
    existing_sectors = {r.sector_name for r in merged_roles}
    for role in additional.market_role_details:
        if role.sector_name not in existing_sectors:
            merged_roles.append(role)
            existing_sectors.add(role.sector_name)

    # 合并别名
    merged_aliases = list(set(base.high_confidence_aliases + additional.high_confidence_aliases))

    # 合并代理候选
    merged_proxies = list(base.proxy_candidates)
    existing_proxy_sectors = {p.get("sector_name", "") for p in merged_proxies}
    for proxy in additional.proxy_candidates:
        if proxy.get("sector_name", "") not in existing_proxy_sectors:
            merged_proxies.append(proxy)
            existing_proxy_sectors.add(proxy.get("sector_name", ""))

    # 合并诊断
    merged_diag = PreparationDiagnostics(
        entity_type=base.diagnostics.entity_type,
        entity_name=base.diagnostics.entity_name,
        target_date=base.diagnostics.target_date,
        window_days=base.diagnostics.window_days,
        repaired_watch_count=max(
            base.diagnostics.repaired_watch_count,
            additional.diagnostics.repaired_watch_count,
        ),
        alias_matches=list(set(
            base.diagnostics.alias_matches + additional.diagnostics.alias_matches
        )),
        theme_matches=base.diagnostics.theme_matches + additional.diagnostics.theme_matches,
        learned_term_matches=(
            base.diagnostics.learned_term_matches + additional.diagnostics.learned_term_matches
        ),
        market_evidence_roles=(
            base.diagnostics.market_evidence_roles + additional.diagnostics.market_evidence_roles
        ),
        proxy_candidates=base.diagnostics.proxy_candidates + additional.diagnostics.proxy_candidates,
        skipped_matches=base.diagnostics.skipped_matches + additional.diagnostics.skipped_matches,
        low_confidence_ignored=(
            base.diagnostics.low_confidence_ignored + additional.diagnostics.low_confidence_ignored
        ),
    )

    # 确定最佳市场角色
    role_priority = {
        EvidenceRole.EXACT_MARKET: 4,
        EvidenceRole.ALIAS_MARKET: 3,
        EvidenceRole.PROXY_MARKET: 2,
        EvidenceRole.NO_MARKET: 1,
    }
    best_role = max(
        [base.market_role, additional.market_role],
        key=lambda r: role_priority.get(r, 0),
    )

    # 确定合并后的置信度
    tier_priority = {
        ConfidenceTier.HIGH: 3,
        ConfidenceTier.MEDIUM: 2,
        ConfidenceTier.LOW: 1,
    }
    best_tier = max(
        [base.confidence_tier, additional.confidence_tier],
        key=lambda t: tier_priority.get(t, 0),
    )

    return SectorPreparationResult(
        sector_name=base.sector_name,
        target_date=base.target_date,
        window_days=base.window_days,
        confidence_tier=best_tier,
        diagnostics=merged_diag,
        market_role=best_role,
        market_role_details=merged_roles,
        high_confidence_aliases=merged_aliases,
        proxy_candidates=merged_proxies,
    )


# ---------------------------------------------------------------------------
# EvidencePreparationService
# ---------------------------------------------------------------------------

class EvidencePreparationService:
    """板块证据准备服务。

    在板块初始化、更新、分组成员变更和分组更新之前自动运行，
    协调以下准备步骤：
    1. CLS 看盘板块归属修复
    2. 已跟踪板块别名刷新
    3. 主题注册表匹配
    4. 已接受学习词条匹配
    5. 市场别名/代理候选发现
    6. 诊断信息聚合
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def prepare_sector(
        self,
        sector_name: str,
        end_date: date,
        window_days: int = 10,
        *,
        skip_repair: bool = False,
    ) -> SectorPreparationResult:
        """为单个板块准备证据。

        Args:
            sector_name: 板块名称
            end_date: 目标结束日期
            window_days: 回看窗口天数
            skip_repair: 是否跳过 CLS 看盘修复

        Returns:
            板块证据准备结果
        """
        canonical = SectorIdentity.normalize(sector_name)
        canonical_key = SectorIdentity.comparison_key(sector_name)

        diagnostics = PreparationDiagnostics(
            entity_type=EntityType.SECTOR,
            entity_name=canonical,
            target_date=end_date.isoformat(),
            window_days=window_days,
        )

        result = SectorPreparationResult(
            sector_name=canonical,
            target_date=end_date.isoformat(),
            window_days=window_days,
            diagnostics=diagnostics,
        )

        # 1. CLS 看盘修复
        if not skip_repair:
            repair_count = await self._repair_watch(canonical, end_date, window_days)
            diagnostics.repaired_watch_count = repair_count

        # 2. 别名发现
        aliases = await self._discover_aliases(canonical, canonical_key)
        result.high_confidence_aliases = aliases
        diagnostics.alias_matches = aliases

        # 3. 主题匹配
        theme_matches = await self._match_themes(canonical, canonical_key, diagnostics)
        diagnostics.theme_matches = theme_matches

        # 4. 已接受学习词条匹配
        learned_matches = await self._match_learned_terms(canonical, canonical_key, diagnostics)
        diagnostics.learned_term_matches = learned_matches

        # 5. 市场证据角色分类
        market_roles = await self._classify_market_evidence(
            canonical, canonical_key, end_date, window_days, aliases, theme_matches,
        )
        result.market_role_details = market_roles
        diagnostics.market_evidence_roles = [
            {"role": r.role.value, "sector_name": r.sector_name, "confidence": r.confidence.value}
            for r in market_roles
        ]

        # 6. 代理候选发现
        proxies = await self._discover_proxy_candidates(
            canonical, canonical_key, end_date, window_days, theme_matches,
        )
        result.proxy_candidates = [
            {"sector_name": p.sector_name, "confidence": p.confidence.value}
            for p in proxies
        ]
        diagnostics.proxy_candidates = [
            {"sector_name": p.sector_name, "confidence": p.confidence.value}
            for p in proxies
        ]

        # 7. 确定最佳市场角色
        if market_roles:
            role_priority = {
                EvidenceRole.EXACT_MARKET: 4,
                EvidenceRole.ALIAS_MARKET: 3,
                EvidenceRole.PROXY_MARKET: 2,
                EvidenceRole.NO_MARKET: 1,
            }
            result.market_role = max(
                market_roles, key=lambda r: role_priority.get(r.role, 0),
            ).role
        else:
            result.market_role = EvidenceRole.NO_MARKET

        # 8. 分类置信度
        result.confidence_tier = classify_confidence_tier(result)

        return result

    async def prepare_group(
        self,
        group_name: str,
        end_date: date,
        window_days: int = 10,
        *,
        skip_repair: bool = False,
    ) -> GroupPreparationResult:
        """为单个分组及其成员准备证据。

        Args:
            group_name: 分组名称
            end_date: 目标结束日期
            window_days: 回看窗口天数
            skip_repair: 是否跳过 CLS 看盘修复

        Returns:
            分组证据准备结果
        """
        diagnostics = PreparationDiagnostics(
            entity_type=EntityType.GROUP,
            entity_name=group_name,
            target_date=end_date.isoformat(),
            window_days=window_days,
        )

        group_result = GroupPreparationResult(
            group_name=group_name,
            target_date=end_date.isoformat(),
            window_days=window_days,
            diagnostics=diagnostics,
        )

        # 加载分组成员
        members = await self._load_group_members(group_name)
        group_result.total_members = len(members)

        # 对每个成员执行准备
        for member_sector_name in members:
            member_result = await self.prepare_sector(
                member_sector_name, end_date, window_days, skip_repair=skip_repair,
            )
            group_result.member_results.append(member_result)

            if member_result.confidence_tier in (ConfidenceTier.HIGH, ConfidenceTier.MEDIUM):
                if member_result.market_role != EvidenceRole.NO_MARKET:
                    group_result.fresh_active_members += 1
                if member_result.market_role == EvidenceRole.PROXY_MARKET:
                    group_result.proxy_backed_members += 1
            else:
                group_result.low_confidence_ignored += 1

        # 识别未解决的缺口
        gaps: list[str] = []
        if not group_result.fresh_active_members:
            gaps.append("no_active_members")
        if group_result.low_confidence_ignored > 0:
            gaps.append(f"{group_result.low_confidence_ignored}_low_confidence_members")
        group_result.unresolved_gaps = gaps

        # 汇总诊断
        diagnostics.repaired_watch_count = max(
            (r.diagnostics.repaired_watch_count for r in group_result.member_results),
            default=0,
        )

        return group_result

    async def prepare_window_shared(
        self,
        end_date: date,
        window_days: int = 10,
    ) -> dict[str, Any]:
        """为指定窗口准备共享证据（如 CLS 看盘修复）。

        批量更新时调用一次，避免每个板块重复修复。

        Args:
            end_date: 目标结束日期
            window_days: 回看窗口天数

        Returns:
            共享准备结果
        """
        try:
            from src.services.cls_watch_repair import ClsWatchRepairService
            repair_service = ClsWatchRepairService(self.db)
            repair_result = await repair_service.repair_window(end_date, window_days)
            return {
                "repair_repaired": repair_result.repaired,
                "repair_unchanged": repair_result.unchanged,
                "repair_unmatched": repair_result.unmatched,
                "repair_low_confidence": repair_result.low_confidence,
            }
        except Exception as e:
            logger.warning("共享窗口 CLS 看盘修复失败: %s", e)
            return {"repair_error": str(e)}

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _repair_watch(
        self, sector_name: str, end_date: date, window_days: int,
    ) -> int:
        """执行 CLS 看盘板块归属修复并返回修复计数。"""
        try:
            from src.services.cls_watch_repair import ClsWatchRepairService
            repair_service = ClsWatchRepairService(self.db)
            repair_result = await repair_service.repair_window(end_date, window_days)
            return repair_result.repaired
        except Exception as e:
            logger.warning("CLS 看盘修复失败: %s", e)
            return 0

    async def _discover_aliases(
        self, canonical_name: str, canonical_key: str,
    ) -> list[str]:
        """从已跟踪板块中发现高置信度别名。"""
        aliases: list[str] = []

        async with self.db.get_session() as session:
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.status.in_(["tracked", "candidate"])
                )
            )
            all_sectors = result.scalars().all()

        for sector in all_sectors:
            if sector.canonical_name == canonical_name:
                continue

            # 检查是否在别名字段中
            if sector.aliases:
                try:
                    alias_list = json.loads(sector.aliases) if isinstance(sector.aliases, str) else sector.aliases
                    if any(SectorIdentity.comparison_key(a) == canonical_key for a in alias_list):
                        aliases.append(sector.canonical_name)
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass

            # 检查名称相似性
            other_key = SectorIdentity.comparison_key(sector.canonical_name)
            if other_key == canonical_key:
                aliases.append(sector.canonical_name)

        return aliases

    async def _match_themes(
        self,
        canonical_name: str,
        canonical_key: str,
        diagnostics: PreparationDiagnostics,
    ) -> list[dict[str, str]]:
        """从主题注册表中匹配相关主题。"""
        try:
            from src.services.theme_registry import ThemeRegistryService
            theme_service = ThemeRegistryService(self.db)
            registry = await theme_service.get_registry()
        except Exception as e:
            logger.warning("主题注册表加载失败: %s", e)
            return []

        matches: list[dict[str, str]] = []

        # 直接主题匹配
        matched_theme = registry.match(canonical_name)
        if matched_theme:
            entry = registry.themes.get(matched_theme)
            if entry:
                matches.append({
                    "theme_name": matched_theme,
                    "source": entry.source,
                    "role": "member",
                })

        # 检查噪声/禁用跳过
        if registry.is_noise(canonical_name):
            diagnostics.skipped_matches.append({
                "term": canonical_name,
                "reason": "noise_term",
                "source": "theme_registry",
            })
        if registry.is_disabled(canonical_name):
            diagnostics.skipped_matches.append({
                "term": canonical_name,
                "reason": "disabled_term",
                "source": "theme_registry",
            })

        return matches

    async def _match_learned_terms(
        self,
        canonical_name: str,
        canonical_key: str,
        diagnostics: PreparationDiagnostics,
    ) -> list[dict[str, str]]:
        """从已接受学习词条中匹配。"""
        matches: list[dict[str, str]] = []

        async with self.db.get_session() as session:
            result = await session.execute(
                select(AcceptedThemeTerm)
            )
            all_terms = result.scalars().all()

        for term in all_terms:
            term_key = SectorIdentity.comparison_key(term.term)
            if term_key == canonical_key:
                matches.append({
                    "theme_name": term.theme_name,
                    "term": term.term,
                    "source": "accepted_learned",
                })

        # 也检查待审定的建议（仅作为低置信度诊断）
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ThemeTermSuggestion).where(
                    ThemeTermSuggestion.status == "pending"
                )
            )
            pending = result.scalars().all()

        for suggestion in pending:
            sug_key = SectorIdentity.comparison_key(suggestion.term)
            if sug_key == canonical_key:
                diagnostics.skipped_matches.append({
                    "term": suggestion.term,
                    "reason": "pending_suggestion_low_confidence_only",
                    "source": "theme_suggestion",
                })

        return matches

    async def _classify_market_evidence(
        self,
        canonical_name: str,
        canonical_key: str,
        end_date: date,
        window_days: int,
        aliases: list[str],
        theme_matches: list[dict[str, str]],
    ) -> list[MarketEvidenceRoleResult]:
        """对市场证据进行角色分类。"""
        start_date = end_date - timedelta(days=window_days)
        roles: list[MarketEvidenceRoleResult] = []

        async with self.db.get_session() as session:
            result = await session.execute(
                select(MarketSector)
                .where(MarketSector.trade_date >= start_date)
                .where(MarketSector.trade_date <= end_date)
            )
            all_market = result.scalars().all()

        # 构建别名键集合
        alias_keys = {SectorIdentity.comparison_key(a) for a in aliases}

        # 构建主题成员键集合（从主题匹配中获取）
        theme_member_keys: set[str] = set()
        try:
            from src.services.theme_registry import ThemeRegistryService
            theme_service = ThemeRegistryService(self.db)
            registry = await theme_service.get_registry()
            for match in theme_matches:
                entry = registry.themes.get(match["theme_name"])
                if entry:
                    for member in entry.members:
                        theme_member_keys.add(SectorIdentity.comparison_key(member))
        except Exception:
            pass

        seen_sectors: set[str] = set()

        for ms in all_market:
            ms_key = SectorIdentity.comparison_key(ms.sector_name)
            if ms_key in seen_sectors:
                continue

            if ms_key == canonical_key:
                # 精确市场证据
                roles.append(MarketEvidenceRoleResult(
                    role=EvidenceRole.EXACT_MARKET,
                    sector_name=ms.sector_name,
                    confidence=ConfidenceTier.HIGH,
                    provenance=PreparationProvenance(
                        source="market_cache",
                        matched_term=ms.sector_name,
                        confidence=ConfidenceTier.HIGH,
                        detail="canonical identity match",
                    ),
                ))
                seen_sectors.add(ms_key)

            elif ms_key in alias_keys:
                # 别名市场证据
                roles.append(MarketEvidenceRoleResult(
                    role=EvidenceRole.ALIAS_MARKET,
                    sector_name=ms.sector_name,
                    confidence=ConfidenceTier.HIGH,
                    provenance=PreparationProvenance(
                        source="alias",
                        matched_term=ms.sector_name,
                        confidence=ConfidenceTier.HIGH,
                        detail="explicit alias match",
                    ),
                ))
                seen_sectors.add(ms_key)

            elif ms_key in theme_member_keys:
                # 代理市场证据（主题成员）
                roles.append(MarketEvidenceRoleResult(
                    role=EvidenceRole.PROXY_MARKET,
                    sector_name=ms.sector_name,
                    confidence=ConfidenceTier.MEDIUM,
                    provenance=PreparationProvenance(
                        source="theme_member",
                        matched_term=ms.sector_name,
                        confidence=ConfidenceTier.MEDIUM,
                        detail="theme member proxy",
                    ),
                ))
                seen_sectors.add(ms_key)

        return roles

    async def _discover_proxy_candidates(
        self,
        canonical_name: str,
        canonical_key: str,
        end_date: date,
        window_days: int,
        theme_matches: list[dict[str, str]],
    ) -> list[MarketEvidenceRoleResult]:
        """发现代理候选（从主题成员、分组成员中查找相关板块的市场数据）。"""
        proxies: list[MarketEvidenceRoleResult] = []

        # 从主题匹配中获取相关成员
        try:
            from src.services.theme_registry import ThemeRegistryService
            theme_service = ThemeRegistryService(self.db)
            registry = await theme_service.get_registry()

            for match in theme_matches:
                entry = registry.themes.get(match["theme_name"])
                if not entry:
                    continue
                for member in entry.members:
                    member_key = SectorIdentity.comparison_key(member)
                    if member_key == canonical_key:
                        continue
                    proxies.append(MarketEvidenceRoleResult(
                        role=EvidenceRole.PROXY_MARKET,
                        sector_name=member,
                        confidence=ConfidenceTier.MEDIUM,
                        provenance=PreparationProvenance(
                            source="theme_member",
                            matched_term=member,
                            confidence=ConfidenceTier.MEDIUM,
                            detail=f"member of theme '{match['theme_name']}'",
                        ),
                    ))
        except Exception:
            pass

        # 从分组成员中获取相关代理
        try:
            async with self.db.get_session() as session:
                # 查找此板块所属的分组
                result = await session.execute(
                    select(SectorGroupMember)
                    .join(SectorGroup)
                    .where(SectorGroup.status == "active")
                )
                all_members = result.scalars().all()

            # 找到此板块所属的分组
            sector_groups: set[int] = set()
            for member in all_members:
                # 获取板块名称
                sector_result = await self.db.get_session()
                async with sector_result as session:
                    ts = await session.execute(
                        select(TrackedSector).where(TrackedSector.id == member.sector_id)
                    )
                    tracked = ts.scalar_one_or_none()
                    if tracked and SectorIdentity.comparison_key(tracked.canonical_name) == canonical_key:
                        sector_groups.add(member.group_id)

            # 从同组其他成员中发现代理
            for member in all_members:
                if member.group_id in sector_groups:
                    async with self.db.get_session() as session:
                        ts = await session.execute(
                            select(TrackedSector).where(TrackedSector.id == member.sector_id)
                        )
                        tracked = ts.scalar_one_or_none()
                        if tracked:
                            other_key = SectorIdentity.comparison_key(tracked.canonical_name)
                            if other_key != canonical_key:
                                proxies.append(MarketEvidenceRoleResult(
                                    role=EvidenceRole.PROXY_MARKET,
                                    sector_name=tracked.canonical_name,
                                    confidence=ConfidenceTier.MEDIUM,
                                    provenance=PreparationProvenance(
                                        source="group_member",
                                        matched_term=tracked.canonical_name,
                                        confidence=ConfidenceTier.MEDIUM,
                                        detail="same group member",
                                    ),
                                ))
        except Exception:
            pass

        return proxies

    async def _load_group_members(self, group_name: str) -> list[str]:
        """加载分组的确认成员板块名称列表。"""
        members: list[str] = []

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroup).where(
                    SectorGroup.canonical_name == group_name
                )
            )
            group = result.scalar_one_or_none()
            if not group:
                return []

            result = await session.execute(
                select(SectorGroupMember)
                .where(SectorGroupMember.group_id == group.id)
            )
            member_records = result.scalars().all()

            for member_record in member_records:
                sector_result = await session.execute(
                    select(TrackedSector).where(TrackedSector.id == member_record.sector_id)
                )
                sector = sector_result.scalar_one_or_none()
                if sector:
                    members.append(sector.canonical_name)

        return members
