## Context

Sector trend reports and sector group trend reports already persist structured labels such as `trend_status`, `strength_level`, `action_bias`, and `judgement`. The current implementation validates that `trend_status` belongs to a supported enum, but the enum values are only described as selectable labels in prompts. This means reports can remain syntactically valid while assigning stages inconsistently.

The planned trend matrix/table work depends on these labels being comparable over time. A row such as `暂无趋势 -> 低位启动 -> 主线延续` should mean the same thing across sectors, groups, and dates. This change therefore treats trend stages as a taxonomy with evidence rules, downgrade rules, and transition constraints.

## Goals / Non-Goals

**Goals:**

- Define single-sector stage semantics for the existing sector `trend_status` enum.
- Define sector-group stage semantics for the existing group `trend_status` enum.
- Standardize shared evidence dimensions used by both levels.
- Prevent sparse, stale, or single-point evidence from producing overconfident stages.
- Constrain group stages using member sector states and member freshness.
- Keep the existing persisted fields and output paths.

**Non-Goals:**

- Do not add a new trend matrix/table command in this change.
- Do not add trading advice or change `action_bias` semantics.
- Do not replace Markdown reports with a new UI.
- Do not require a database migration.
- Do not backfill or rewrite historical labels.

## Decisions

### 1. Keep Existing Enums, Add Definitions

The implementation should retain the existing sector enum:

```text
主线加强 / 主线延续 / 分歧中继 / 低位启动 / 轮动补涨 / 短线脉冲 / 高位退潮 / 暂无趋势
```

And the existing group enum:

```text
主线共振 / 主线扩散 / 轮动分化 / 低位启动 / 补涨蔓延 / 短线脉冲 / 高位退潮 / 暂无趋势
```

Rationale: existing reports, tests, and storage already depend on these labels. Replacing the enum would create unnecessary churn. The problem is not the label set; it is the lack of strict meaning behind each label.

Alternative considered: create a new numeric stage model. This would be easier to sort, but it would hide important market-structure distinctions such as `轮动分化` versus `补涨蔓延`.

### 2. Use Shared Evidence Dimensions

Both sector and group stages should be evaluated through a common evidence model:

- evidence sufficiency: whether the report has enough market/watch/telegraph/member evidence
- continuity: whether activity persists across more than one day
- strength: price/rank/fund/attention strength where available
- breadth: number of related members or signals participating
- freshness: whether evidence and member reports match the target date/window
- prior-state context: the previous trend label and judgement
- retreat signals: weakening, divergence, stale activity, or broad rollback

Rationale: this keeps sector and group stages aligned without pretending that a group is just a larger sector.

### 3. Prompt Rules First, Service Guardrails Second

Prompts should include the full taxonomy and ask the AI to select the most constrained valid label. Service-level validation should then guard against obvious violations, such as sparse evidence producing `主线加强` or a group with mostly missing member summaries producing `主线共振`.

Rationale: the AI can still interpret qualitative evidence, but deterministic guardrails prevent the most damaging label drift.

Alternative considered: fully deterministic stage assignment. This is premature because the current evidence is still mixed and partly qualitative. The first implementation should combine strict prompt definitions with conservative service validation.

### 4. Treat Sparse Evidence as a Hard Downgrade

Sparse evidence should not merely be mentioned in report text. It should restrict allowed stages.

For single sectors, sparse evidence should allow only `暂无趋势` or `短线脉冲` unless there is sufficient prior-state and current-window evidence to justify continuity.

For groups, missing or stale member summaries should restrict allowed group stages, especially `主线共振`, `主线扩散`, and `补涨蔓延`.

Rationale: overconfident labels are worse than conservative labels because future trend tables become misleading.

### 5. Stage Transitions Need Prior Context

Some stages imply a previous state:

- `主线加强` requires an existing active trend or strong multi-day window evidence.
- `主线延续` requires prior trend context or enough in-window continuity.
- `高位退潮` requires a prior active/high stage or clear current-window retreat from a previously active state.
- first-time reports should usually prefer `暂无趋势`, `短线脉冲`, or `低位启动` unless the evidence window itself proves a mature trend.

Rationale: stage labels describe movement through time, not only a static snapshot.

### 6. Group Stages Must Be Member-Compatible

Group stages should be constrained by member sector labels and freshness:

- `主线共振` requires multiple fresh active members.
- `主线扩散` requires a core member plus fresh evidence of peripheral members joining.
- `轮动分化` requires mixed member states with some active and some weakening/stale.
- `补涨蔓延` requires core activity plus catch-up activity from non-core or previously weaker members.
- `高位退潮` requires core weakening or broad member weakening.

Rationale: group labels are structural labels. They should not be assigned from a single member's report alone.

## Risks / Trade-offs

- [Risk] Existing historical labels may not satisfy the new taxonomy. → Mitigation: apply the taxonomy only to newly generated reports; historical records remain as-is.
- [Risk] Too many hard rules could downgrade legitimate early themes. → Mitigation: allow `低位启动` when evidence is fresh and multi-signal, even without prior state.
- [Risk] Evidence sources are incomplete today. → Mitigation: make insufficient evidence explicit and conservative, rather than inventing confidence.
- [Risk] Service validation may conflict with AI-written narrative. → Mitigation: prompts should include the same rules used by validation, and tests should cover downgraded labels.
- [Risk] Group stages can be distorted by stale member summaries. → Mitigation: member freshness becomes a formal stage constraint.
