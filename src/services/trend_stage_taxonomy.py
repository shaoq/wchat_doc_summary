"""趋势阶段分类法 — 板块和分组的趋势阶段定义、证据维度、降级规则和转换约束。

本模块为 sector trend 和 group trend 的 `trend_status` 标签提供统一的语义定义，
确保标签在不同日期、不同板块和不同分组之间具有可比性。
"""

from __future__ import annotations

from typing import FrozenSet, Tuple

# ---------------------------------------------------------------------------
# 1.1 单板块趋势阶段
# ---------------------------------------------------------------------------

SECTOR_TREND_STAGES: Tuple[str, ...] = (
    "主线加强",
    "主线延续",
    "分歧中继",
    "低位启动",
    "轮动补涨",
    "短线脉冲",
    "高位退潮",
    "暂无趋势",
)

SECTOR_STAGE_DEFINITIONS: dict[str, str] = {
    "主线加强": (
        "已有确认的趋势（主线延续/分歧中继/轮动补涨/低位启动），且当前窗口证据显示 "
        "强度或多信号参与度显著提升。需要：先前的活跃阶段上下文，或多日窗口中持续加强的证据。"
    ),
    "主线延续": (
        "趋势持续活跃，但未出现明显加强或分歧。需要：先前确认的活跃趋势上下文，"
        "或窗口内足够的连续性证据证明趋势延续。"
    ),
    "分歧中继": (
        "趋势仍在，但出现方向分歧信号（如板块内个股分化、资金流向不一致）。"
        "需要：先前活跃趋势上下文，且当前窗口证据显示多空信号并存。"
    ),
    "低位启动": (
        "新兴的多信号活跃迹象，但尚无先前确认的趋势上下文。需要：新鲜的行情证据 "
        "加上至少一个佐证信息源，或多次行情出现记录。不得在没有新鲜多信号证据时使用。"
    ),
    "轮动补涨": (
        "该板块作为轮动或补涨方向被激活，而非主线驱动。需要：行情证据显示该板块 "
        "在其他板块已走强后才开始活跃，且活跃证据是新鲜的。"
    ),
    "短线脉冲": (
        "单日或极短窗口的孤立行情，缺乏连续性和广度。仅用于短暂的单次活跃事件，"
        "不隐含趋势方向。不要求先前上下文。"
    ),
    "高位退潮": (
        "先前活跃的趋势正在减弱。需要：先前的活跃/高位阶段上下文，或当前窗口 "
        "证据显示从先前活跃状态退潮。无先前活跃上下文时不得使用。"
    ),
    "暂无趋势": (
        "无足够证据表明该板块存在趋势。证据稀疏、缺失或无方向性时使用。"
        "始终是保守的默认选择。"
    ),
}

# 需要先前活跃上下文的阶段
SECTOR_PRIOR_REQUIRED_STAGES: FrozenSet[str] = frozenset({
    "主线加强", "主线延续", "分歧中继", "高位退潮",
})

# 先前的活跃阶段（可用于满足 prior-required 条件）
SECTOR_ACTIVE_PRIOR_STAGES: FrozenSet[str] = frozenset({
    "低位启动", "主线延续", "分歧中继", "轮动补涨",
})

# 首次报告允许的阶段
SECTOR_FIRST_REPORT_ALLOWED: FrozenSet[str] = frozenset({
    "暂无趋势", "短线脉冲", "低位启动",
})

# 稀疏证据允许的阶段
SECTOR_SPARSE_ALLOWED: FrozenSet[str] = frozenset({
    "暂无趋势", "短线脉冲",
})

# 缺少行情证据时禁止的阶段
SECTOR_NO_MARKET_FORBIDDEN: FrozenSet[str] = frozenset({
    "主线加强", "主线延续", "低位启动",
})

# ---------------------------------------------------------------------------
# 1.2 分组趋势阶段
# ---------------------------------------------------------------------------

GROUP_TREND_STAGES: Tuple[str, ...] = (
    "主线共振",
    "主线扩散",
    "轮动分化",
    "低位启动",
    "补涨蔓延",
    "短线脉冲",
    "高位退潮",
    "暂无趋势",
)

GROUP_STAGE_DEFINITIONS: dict[str, str] = {
    "主线共振": (
        "多个确认成员同时处于活跃趋势状态。需要：多个新鲜且活跃的成员板块，"
        "且至少一个核心/高权重成员为活跃状态。不得仅凭单一成员使用。"
    ),
    "主线扩散": (
        "趋势从核心成员向周边成员扩散。需要：核心/高权重成员已活跃，且有新鲜证据 "
        "显示相关、上下游、催化或低权重成员正在加入。"
    ),
    "轮动分化": (
        "成员状态混合——部分活跃、部分走弱/过期/暂无趋势。需要：证据显示 "
        "板块间轮动且方向不一致，而非全组同步。"
    ),
    "低位启动": (
        "分组整体出现新兴活跃迹象，但尚无先前确认的分组趋势。需要：多个成员 "
        "出现新鲜的活跃信号，但不足以判定共振。"
    ),
    "补涨蔓延": (
        "非核心/下游/相关或先前较弱的成员在核心成员之后开始活跃。需要：证据显示 "
        "补涨活动且能区分补涨成员与核心成员。"
    ),
    "短线脉冲": (
        "短暂的分组活跃，缺乏多成员参与和持续性。仅用于短暂的单次活跃事件。"
    ),
    "高位退潮": (
        "核心成员走弱或广泛成员退化。需要：先前活跃的分组趋势上下文，"
        "或当前窗口证据显示从先前活跃状态退潮。无先前活跃上下文时不得使用。"
    ),
    "暂无趋势": (
        "无足够证据表明该分组存在结构性趋势。成员缺失、过期或无方向性时使用。"
    ),
}

# 需要多成员参与的分组阶段
GROUP_MULTI_MEMBER_STAGES: FrozenSet[str] = frozenset({
    "主线共振", "主线扩散", "补涨蔓延",
})

# 需要先前活跃上下文的分组阶段
GROUP_PRIOR_REQUIRED_STAGES: FrozenSet[str] = frozenset({
    "高位退潮",
})

# 分组成员的活跃板块状态（用于判断共振条件）
GROUP_MEMBER_ACTIVE_SECTOR_STAGES: FrozenSet[str] = frozenset({
    "低位启动", "轮动补涨", "主线延续", "主线加强", "分歧中继",
})

# 稀疏/缺失成员时允许的分组阶段
GROUP_SPARSE_MEMBER_ALLOWED: FrozenSet[str] = frozenset({
    "暂无趋势", "短线脉冲",
})

# 单一活跃成员时允许的分组阶段
GROUP_SINGLE_ACTIVE_ALLOWED: FrozenSet[str] = frozenset({
    "短线脉冲", "低位启动", "暂无趋势",
})

# ---------------------------------------------------------------------------
# 1.3 共享证据维度
# ---------------------------------------------------------------------------

EVIDENCE_DIMENSIONS: dict[str, str] = {
    "evidence_sufficiency": "报告是否拥有足够的市场/看盘/电报/成员证据",
    "continuity": "活跃是否跨越多日持续存在",
    "strength": "价格/排名/资金/关注度强度",
    "breadth": "参与的相关成员或信号数量",
    "freshness": "证据和成员报告是否匹配目标日期/窗口",
    "prior_state_context": "先前的趋势标签和研判",
    "retreat_signals": "走弱、分歧、过期活跃或广泛回退信号",
}

# ---------------------------------------------------------------------------
# 1.4 阶段转换约束
# ---------------------------------------------------------------------------

# 转换约束说明：某些阶段在特定条件下不允许被选中。
# 约束通过 validate_sector_stage / validate_group_stage 函数实现。


def validate_sector_stage(
    stage: str,
    *,
    is_sparse: bool = False,
    has_market_evidence: bool = True,
    has_prior: bool = False,
    prior_stage: str | None = None,
    is_first_report: bool = False,
    has_multi_signal_fresh: bool = False,
) -> str:
    """验证板块趋势阶段，返回可能被降级的阶段。

    Args:
        stage: AI 提议的趋势阶段
        is_sparse: 证据是否稀疏
        has_market_evidence: 是否有行情证据
        has_prior: 是否有先前总结
        prior_stage: 先前的趋势阶段
        is_first_report: 是否为首次报告
        has_multi_signal_fresh: 是否有新鲜多信号证据

    Returns:
        验证后（可能降级的）趋势阶段
    """
    if stage not in SECTOR_STAGE_DEFINITIONS:
        return "暂无趋势"

    # 首次报告约束
    if is_first_report and stage not in SECTOR_FIRST_REPORT_ALLOWED:
        if has_multi_signal_fresh and stage == "低位启动":
            return stage
        if has_multi_signal_fresh and stage in ("主线延续", "分歧中继"):
            # 仅当窗口内证据充分证明连续性时允许
            return stage
        return "暂无趋势"

    # 稀疏证据降级
    if is_sparse and stage not in SECTOR_SPARSE_ALLOWED:
        # 除非有先前上下文且为延续型
        if has_prior and prior_stage in SECTOR_ACTIVE_PRIOR_STAGES:
            if stage == "主线延续":
                return stage
        return "暂无趋势"

    # 缺少行情证据降级
    if not has_market_evidence and stage in SECTOR_NO_MARKET_FORBIDDEN:
        return "暂无趋势"

    # 需要先前上下文的阶段
    if stage in SECTOR_PRIOR_REQUIRED_STAGES:
        if not has_prior:
            # 无先前上下文，但窗口内证据可能充分
            if has_multi_signal_fresh and stage in ("主线延续", "分歧中继"):
                return stage
            return "暂无趋势"
        if prior_stage not in SECTOR_ACTIVE_PRIOR_STAGES and prior_stage != stage:
            # 先前非活跃阶段
            if stage == "高位退潮" and prior_stage in ("主线加强",):
                return stage
            if has_multi_signal_fresh and stage in ("主线延续", "分歧中继"):
                return stage
            if stage == "主线加强" and prior_stage in SECTOR_ACTIVE_PRIOR_STAGES:
                return stage
            return "暂无趋势"

    return stage


def validate_group_stage(
    stage: str,
    *,
    member_freshness: list[dict] | None = None,
    member_sectors: list[dict] | None = None,
    has_prior: bool = False,
    prior_stage: str | None = None,
) -> str:
    """验证分组趋势阶段，返回可能被降级的阶段。

    Args:
        stage: AI 提议的分组趋势阶段
        member_freshness: 成员新鲜度列表，每项包含 is_fresh, sector_status 等
        member_sectors: 成员板块报告列表，每项包含 trend_status, relation_type 等
        has_prior: 是否有先前分组总结
        prior_stage: 先前的分组趋势阶段

    Returns:
        验证后（可能降级的）分组趋势阶段
    """
    if stage not in GROUP_STAGE_DEFINITIONS:
        return "暂无趋势"

    freshness = member_freshness or []
    sectors = member_sectors or []

    fresh_members = [m for m in freshness if m.get("is_fresh", False)]
    active_members = [
        s for s in sectors
        if s.get("trend_status", "") in GROUP_MEMBER_ACTIVE_SECTOR_STAGES
    ]
    confirmed_members = [
        s for s in sectors if s.get("sector_status") != "candidate"
    ]
    fresh_active_confirmed = [
        s for s in confirmed_members
        if s.get("is_fresh", False)
        and s.get("trend_status", "") in GROUP_MEMBER_ACTIVE_SECTOR_STAGES
    ]

    # 无新鲜成员 → 严重降级
    if not fresh_members:
        return "暂无趋势"

    # 大部分成员过期 → 禁止共振/扩散
    stale_ratio = 1 - len(fresh_members) / max(len(freshness), 1)
    if stale_ratio > 0.5 and stage in GROUP_MULTI_MEMBER_STAGES:
        return "暂无趋势"

    # 候选成员为主 → 禁止共振/扩散/补涨（优先于单活跃检查）
    candidate_ratio = (
        len([s for s in sectors if s.get("sector_status") == "candidate"])
        / max(len(sectors), 1)
    )
    if candidate_ratio > 0.5 and stage in GROUP_MULTI_MEMBER_STAGES:
        return "暂无趋势"

    # 仅单一活跃确认成员 → 限制到单成员允许集
    if len(fresh_active_confirmed) <= 1 and stage in GROUP_MULTI_MEMBER_STAGES:
        return "暂无趋势" if not fresh_active_confirmed else "短线脉冲"

    # 高位退潮需要先前活跃上下文
    if stage == "高位退潮":
        if not has_prior or prior_stage not in (
            GROUP_MULTI_MEMBER_STAGES | {"低位启动", "短线脉冲"}
        ):
            return "暂无趋势"

    return stage
