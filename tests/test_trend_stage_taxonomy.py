"""趋势阶段分类法测试 - 覆盖板块/分组阶段验证、降级规则、转换约束、模板内容检查。"""

import pytest

from src.services.trend_stage_taxonomy import (
    SECTOR_TREND_STAGES,
    SECTOR_STAGE_DEFINITIONS,
    SECTOR_SPARSE_ALLOWED,
    SECTOR_FIRST_REPORT_ALLOWED,
    SECTOR_PRIOR_REQUIRED_STAGES,
    SECTOR_ACTIVE_PRIOR_STAGES,
    GROUP_TREND_STAGES,
    GROUP_STAGE_DEFINITIONS,
    GROUP_MULTI_MEMBER_STAGES,
    GROUP_MEMBER_ACTIVE_SECTOR_STAGES,
    GROUP_SPARSE_MEMBER_ALLOWED,
    GROUP_SINGLE_ACTIVE_ALLOWED,
    EVIDENCE_DIMENSIONS,
    validate_sector_stage,
    validate_group_stage,
)


# ===========================================================================
# 4.1 板块稀疏证据降级行为
# ===========================================================================


class TestSectorSparseEvidenceDowngrade:
    """板块稀疏证据降级测试。"""

    def test_sparse_evidence_allows_only_conservative_stages(self):
        """稀疏证据只允许暂无趋势和短线脉冲。"""
        for stage in SECTOR_TREND_STAGES:
            result = validate_sector_stage(stage, is_sparse=True)
            if stage in SECTOR_SPARSE_ALLOWED:
                assert result == stage, f"稀疏证据应允许 {stage}"
            else:
                assert result == "暂无趋势", f"稀疏证据应降级 {stage} → 暂无趋势"

    def test_sparse_with_prior_continuation_allowed(self):
        """稀疏证据 + 先前活跃上下文 + 主线延续 → 允许延续。"""
        result = validate_sector_stage(
            "主线延续", is_sparse=True, has_prior=True, prior_stage="低位启动",
        )
        assert result == "主线延续"

    def test_sparse_without_prior_downgrade(self):
        """稀疏证据 + 无先前上下文 → 降级。"""
        result = validate_sector_stage("主线加强", is_sparse=True, has_prior=False)
        assert result == "暂无趋势"

    def test_no_market_evidence_blocks_mainline(self):
        """无行情证据 → 禁止主线加强/主线延续/低位启动。"""
        forbidden = {"主线加强", "主线延续", "低位启动"}
        for stage in forbidden:
            result = validate_sector_stage(stage, has_market_evidence=False)
            assert result == "暂无趋势", f"无行情证据应降级 {stage}"

    def test_no_market_evidence_allows_pulse(self):
        """无行情证据 → 允许短线脉冲。"""
        result = validate_sector_stage("短线脉冲", has_market_evidence=False)
        assert result == "短线脉冲"

    def test_sufficient_evidence_allows_all(self):
        """充分证据 + 先前上下文 → 允许所有阶段。"""
        for stage in SECTOR_TREND_STAGES:
            result = validate_sector_stage(
                stage,
                is_sparse=False,
                has_market_evidence=True,
                has_prior=True,
                prior_stage="主线延续",
            )
            assert result == stage, f"充分证据+先前上下文应允许 {stage}"


# ===========================================================================
# 4.2 板块阶段转换约束
# ===========================================================================


class TestSectorStageTransitions:
    """板块阶段转换约束测试。"""

    def test_first_report_conservative(self):
        """首次报告只能选择保守阶段。"""
        for stage in SECTOR_TREND_STAGES:
            result = validate_sector_stage(stage, is_first_report=True)
            if stage in SECTOR_FIRST_REPORT_ALLOWED:
                assert result == stage, f"首次报告应允许 {stage}"
            else:
                assert result == "暂无趋势", f"首次报告应降级 {stage}"

    def test_first_report_with_multi_signal_allows_startup(self):
        """首次报告 + 多信号新鲜证据 → 允许低位启动。"""
        result = validate_sector_stage(
            "低位启动", is_first_report=True, has_multi_signal_fresh=True,
        )
        assert result == "低位启动"

    def test_first_report_with_multi_signal_allows_continuation(self):
        """首次报告 + 多信号新鲜证据 → 允许主线延续（窗口内证据充分）。"""
        result = validate_sector_stage(
            "主线延续", is_first_report=True, has_multi_signal_fresh=True,
        )
        assert result == "主线延续"

    def test_mainline_strengthening_requires_prior(self):
        """主线加强需要先前活跃上下文。"""
        # 无先前
        result = validate_sector_stage("主线加强", has_prior=False)
        assert result == "暂无趋势"

        # 先前为活跃阶段
        for prior in SECTOR_ACTIVE_PRIOR_STAGES:
            result = validate_sector_stage(
                "主线加强", has_prior=True, prior_stage=prior,
            )
            assert result == "主线加强", f"先前 {prior} 应允许主线加强"

    def test_mainline_continuation_requires_prior(self):
        """主线延续需要先前上下文或充分窗口证据。"""
        result = validate_sector_stage("主线延续", has_prior=False)
        assert result == "暂无趋势"

        result = validate_sector_stage(
            "主线延续", has_prior=True, prior_stage="低位启动",
        )
        assert result == "主线延续"

    def test_retreat_requires_prior_active(self):
        """高位退潮需要先前活跃上下文。"""
        result = validate_sector_stage("高位退潮", has_prior=False)
        assert result == "暂无趋势"

        # 先前为主线加强也应允许退潮
        result = validate_sector_stage(
            "高位退潮", has_prior=True, prior_stage="主线加强",
        )
        assert result == "高位退潮"

    def test_retreat_no_prior_active_downgrades(self):
        """高位退潮 + 先前为暂无趋势 → 降级。"""
        result = validate_sector_stage(
            "高位退潮", has_prior=True, prior_stage="暂无趋势",
        )
        assert result == "暂无趋势"

    def test_invalid_stage_returns_no_trend(self):
        """无效阶段返回暂无趋势。"""
        result = validate_sector_stage("无效阶段")
        assert result == "暂无趋势"


# ===========================================================================
# 4.3 分组成员新鲜度降级行为
# ===========================================================================


class TestGroupMemberFreshnessDowngrade:
    """分组成员新鲜度降级测试。"""

    def test_no_fresh_members_downgrade(self):
        """无新鲜成员 → 暂无趋势。"""
        result = validate_group_stage(
            "主线共振",
            member_freshness=[{"sector_name": "A", "is_fresh": False}],
            member_sectors=[{"trend_status": "主线延续", "sector_status": "tracked"}],
        )
        assert result == "暂无趋势"

    def test_stale_majority_blocks_resonance(self):
        """大部分成员过期 → 禁止共振。"""
        freshness = [
            {"sector_name": "A", "is_fresh": True},
            {"sector_name": "B", "is_fresh": False},
            {"sector_name": "C", "is_fresh": False},
        ]
        result = validate_group_stage(
            "主线共振", member_freshness=freshness, member_sectors=[],
        )
        assert result == "暂无趋势"

    def test_fresh_members_allow_resonance(self):
        """新鲜成员充足 → 允许共振。"""
        freshness = [
            {"sector_name": "A", "is_fresh": True},
            {"sector_name": "B", "is_fresh": True},
        ]
        sectors = [
            {"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True},
            {"trend_status": "低位启动", "sector_status": "tracked", "is_fresh": True},
        ]
        result = validate_group_stage(
            "主线共振", member_freshness=freshness, member_sectors=sectors,
        )
        assert result == "主线共振"


# ===========================================================================
# 4.4 分组成员一致性约束
# ===========================================================================


class TestGroupMemberConsistency:
    """分组成员一致性约束测试。"""

    def test_single_active_blocks_multi_member_stages(self):
        """单一活跃成员 → 禁止多成员阶段。"""
        for stage in GROUP_MULTI_MEMBER_STAGES:
            sectors = [
                {"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True},
            ]
            freshness = [{"sector_name": "A", "is_fresh": True}]

            result = validate_group_stage(
                stage, member_freshness=freshness, member_sectors=sectors,
            )
            assert result in GROUP_SINGLE_ACTIVE_ALLOWED, (
                f"单一活跃成员应降级 {stage}"
            )

    def test_candidate_dominance_blocks_resonance(self):
        """候选成员为主 → 禁止共振/扩散/补涨。"""
        sectors = [
            {"trend_status": "主线延续", "sector_status": "candidate", "is_fresh": True},
            {"trend_status": "低位启动", "sector_status": "candidate", "is_fresh": True},
            {"trend_status": "主线加强", "sector_status": "tracked", "is_fresh": True},
        ]
        freshness = [
            {"sector_name": "A", "is_fresh": True},
            {"sector_name": "B", "is_fresh": True},
            {"sector_name": "C", "is_fresh": True},
        ]

        for stage in GROUP_MULTI_MEMBER_STAGES:
            result = validate_group_stage(
                stage, member_freshness=freshness, member_sectors=sectors,
            )
            assert result == "暂无趋势", f"候选为主应降级 {stage}"

    def test_resonance_requires_multiple_active(self):
        """主线共振需要多个活跃确认成员。"""
        # 只有1个活跃 → 降级（允许 短线脉冲/暂无趋势）
        sectors = [
            {"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True},
            {"trend_status": "暂无趋势", "sector_status": "tracked", "is_fresh": True},
        ]
        freshness = [
            {"sector_name": "A", "is_fresh": True},
            {"sector_name": "B", "is_fresh": True},
        ]
        result = validate_group_stage(
            "主线共振", member_freshness=freshness, member_sectors=sectors,
        )
        assert result in ("暂无趋势", "短线脉冲")

        # 2个活跃 → 允许共振
        sectors2 = [
            {"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True},
            {"trend_status": "低位启动", "sector_status": "tracked", "is_fresh": True},
        ]
        result = validate_group_stage(
            "主线共振", member_freshness=freshness, member_sectors=sectors2,
        )
        assert result == "主线共振"

    def test_group_retreat_requires_prior(self):
        """分组高位退潮需要先前活跃上下文。"""
        result = validate_group_stage(
            "高位退潮",
            has_prior=False,
            member_freshness=[{"sector_name": "A", "is_fresh": True}],
            member_sectors=[{"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True}],
        )
        assert result == "暂无趋势"

    def test_group_retreat_with_prior_active(self):
        """分组高位退潮 + 先前共振 → 允许。"""
        result = validate_group_stage(
            "高位退潮",
            has_prior=True,
            prior_stage="主线共振",
            member_freshness=[{"sector_name": "A", "is_fresh": True}],
            member_sectors=[{"trend_status": "主线延续", "sector_status": "tracked", "is_fresh": True}],
        )
        assert result == "高位退潮"

    def test_invalid_group_stage_returns_no_trend(self):
        """无效分组阶段返回暂无趋势。"""
        result = validate_group_stage("无效阶段")
        assert result == "暂无趋势"


# ===========================================================================
# 4.5 模板/提示词测试
# ===========================================================================


class TestPromptTemplates:
    """模板内容测试。"""

    def test_sector_template_includes_stage_definitions(self):
        """板块模板包含阶段定义。"""
        from pathlib import Path

        template = Path("templates/sector_trend_summary.md").read_text(encoding="utf-8")
        for stage in SECTOR_TREND_STAGES:
            assert stage in template, f"板块模板缺少阶段定义: {stage}"

    def test_sector_template_includes_downgrade_rules(self):
        """板块模板包含降级规则。"""
        from pathlib import Path

        template = Path("templates/sector_trend_summary.md").read_text(encoding="utf-8")
        assert "降级规则" in template
        assert "稀疏证据" in template

    def test_sector_template_treats_status_as_descriptive(self):
        """板块模板将 trend_status 描述为描述性标签。"""
        from pathlib import Path

        template = Path("templates/sector_trend_summary.md").read_text(encoding="utf-8")
        assert "描述性" in template or "不是推荐" in template or "不是交易建议" in template

    def test_group_template_includes_stage_definitions(self):
        """分组模板包含阶段定义。"""
        from pathlib import Path

        template = Path("templates/sector_group_trend_summary.md").read_text(encoding="utf-8")
        for stage in GROUP_TREND_STAGES:
            assert stage in template, f"分组模板缺少阶段定义: {stage}"

    def test_group_template_includes_downgrade_rules(self):
        """分组模板包含降级规则。"""
        from pathlib import Path

        template = Path("templates/sector_group_trend_summary.md").read_text(encoding="utf-8")
        assert "降级规则" in template
        assert "新鲜成员" in template or "成员报告不足" in template

    def test_group_template_treats_status_as_descriptive(self):
        """分组模板将 trend_status 描述为描述性标签。"""
        from pathlib import Path

        template = Path("templates/sector_group_trend_summary.md").read_text(encoding="utf-8")
        assert "描述性" in template or "不是交易建议" in template


# ===========================================================================
# 额外: 分类法常量完整性检查
# ===========================================================================


class TestTaxonomyCompleteness:
    """分类法定义完整性检查。"""

    def test_all_sector_stages_have_definitions(self):
        """所有板块阶段都有定义。"""
        for stage in SECTOR_TREND_STAGES:
            assert stage in SECTOR_STAGE_DEFINITIONS, f"缺少定义: {stage}"

    def test_all_group_stages_have_definitions(self):
        """所有分组阶段都有定义。"""
        for stage in GROUP_TREND_STAGES:
            assert stage in GROUP_STAGE_DEFINITIONS, f"缺少定义: {stage}"

    def test_evidence_dimensions_complete(self):
        """证据维度定义完整。"""
        expected_dims = {
            "evidence_sufficiency", "continuity", "strength",
            "breadth", "freshness", "prior_state_context", "retreat_signals",
        }
        assert set(EVIDENCE_DIMENSIONS.keys()) == expected_dims

    def test_sector_enum_preserved(self):
        """板块枚举值与原有一致。"""
        expected = ("主线加强", "主线延续", "分歧中继", "低位启动",
                    "轮动补涨", "短线脉冲", "高位退潮", "暂无趋势")
        assert SECTOR_TREND_STAGES == expected

    def test_group_enum_preserved(self):
        """分组枚举值与原有一致。"""
        expected = ("主线共振", "主线扩散", "轮动分化", "低位启动",
                    "补涨蔓延", "短线脉冲", "高位退潮", "暂无趋势")
        assert GROUP_TREND_STAGES == expected
