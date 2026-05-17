## Context

The sector trend system now has several evidence inputs: market sector cache rows, repaired CLS watch sector tags, CLS telegraphs, sector group themes, accepted learned theme terms, tracked sector aliases, and member sector summaries. These inputs are useful only when they are connected to the sector or group being analyzed.

The current workflow can still fail for new sectors or groups:

- A newly initialized sector may have no exact `market_sectors` row even though related or proxy market rows exist.
- A group member may have watch/telegraph activity but remain structurally inactive because its final `trend_status` was downgraded due to exact market evidence absence.
- Users currently need to know which repair or theme commands to run after adding sectors or group members.

This change introduces an automatic preparation layer that runs before evidence is consumed. It should prepare data, classify confidence, and expose diagnostics without silently over-promoting weak matches.

## Goals / Non-Goals

**Goals:**

- Run evidence preparation automatically during sector init, sector update, group member changes, and group update.
- Repair relevant CLS watch sector attribution without requiring a separate manual command.
- Build or refresh aliases, theme links, and market proxy candidates for new sectors and group members.
- Distinguish exact, alias, and proxy market evidence roles during sector evidence collection.
- Allow group trend validation to consider member evidence quality and proxy-backed activity, not only final member labels.
- Persist or return preparation diagnostics so users can audit what happened.
- Keep low-confidence evidence from promoting trend stages.

**Non-Goals:**

- Do not automatically fetch missing remote market or CLS data.
- Do not automatically merge related sectors into the same identity.
- Do not treat every theme member as an exact market alias.
- Do not remove manual repair, theme, or suggestion review commands.
- Do not broadly relax trend-stage validation; update validation inputs so high-confidence proxy evidence is visible.

## Decisions

### 1. Introduce a Shared EvidencePreparationService

Create a service that can be invoked from sector and group workflows. It should accept a target entity, date/window, and mode, then coordinate:

- CLS watch sector repair for the window
- tracked-sector alias refresh
- theme registry matching
- accepted learned term matching
- market alias/proxy candidate discovery
- diagnostics aggregation

Rationale: preparation crosses sector tracking, group tracking, and theme learning. A shared service keeps behavior consistent and avoids each command implementing its own partial preparation logic.

Alternative considered: run only the existing watch repair in update commands. This does not solve market proxy evidence gaps or new group-member preparation.

### 2. Use Evidence Roles Instead of Binary Market Presence

Sector evidence should classify market evidence as:

```text
exact_market  -> same canonical sector identity
alias_market  -> explicit alias or accepted equivalent identity
proxy_market  -> related theme/member/proxy sector evidence
no_market     -> no usable market evidence
```

Only `exact_market` and high-confidence `alias_market` should behave like direct market evidence. `proxy_market` should support continuity and diagnostics, and may satisfy selected validation gates only when combined with multi-source confirmation.

Rationale: current binary `has_market_evidence` turns strong watch/telegraph-only themes into `暂无趋势`. Evidence roles let validation remain conservative while avoiding false "data missing" conclusions.

Alternative considered: simply remove the no-market downgrade. That would over-promote text-only themes and undermine the stage taxonomy.

### 3. Confidence Tiers Control Automation

Preparation outputs should be categorized:

- high confidence: exact IDs, explicit aliases, accepted learned terms, strong theme membership with supporting evidence
- medium confidence: theme/proxy matches with partial supporting evidence
- low confidence: weak text-only or ambiguous matches

High-confidence outputs can be persisted and used for trend judgement. Medium-confidence outputs can be stored as weak/proxy evidence and diagnostics. Low-confidence outputs should not promote trend stages and should remain reviewable.

Rationale: automatic execution is useful only if it remains bounded by confidence.

Alternative considered: require manual review for all new mappings. That is safer but violates the user goal that preparation happens automatically.

### 4. Group Validation Should Read Member Evidence Quality

Group validation should consider fresh member summaries plus member evidence quality:

- direct active member labels
- high-confidence proxy-backed member activity
- source breadth across watch, telegraph, and market/proxy market
- member freshness for the target date

Rationale: a group can be structurally active even when a member's final sector label was conservatively downgraded due to exact market evidence absence. The group validator still needs guardrails, but it should not rely only on final member `trend_status`.

Alternative considered: force member sector stages to active whenever group evidence is active. That creates circular reinforcement and can corrupt single-sector history.

### 5. Automatic Preparation Runs by Default, Manual Controls Remain

Default behavior:

- `sector-trends init` prepares the new sector but does not generate a report.
- `sector-trends update` prepares the target window before generation.
- `groups add` prepares the group/member relationship but does not generate a group report.
- `groups update` prepares group and member evidence before member refresh and group generation.

Manual repair and diagnostics commands remain available for backfills and troubleshooting. Skip flags can be retained for debugging.

Rationale: default automation matches user expectations while manual controls support reproducibility and audit.

### 6. Final Labels Must Be Synchronized After Validation

Trend generation currently has two label moments:

```text
AI raw label -> service validation/downgrade -> persisted structured label
```

After this change, the validated final label must be the single source of truth for:

- database summary fields
- Markdown report `结构化标签`
- CLI result rows
- downstream group member evidence
- trend matrix/history consumers

If validation changes a label, the report content must be rewritten or rendered with the final labels before saving. The original AI-proposed label can be retained in diagnostics, but it must not appear as the authoritative report label.

Rationale: current reports can say `主线共振` in Markdown while the database stores `暂无趋势`, which makes debugging and downstream group validation misleading.

Alternative considered: keep Markdown as the AI's original narrative and treat database as authoritative. That preserves raw output but creates user-visible contradictions and breaks report-based review.

## Risks / Trade-offs

- [Risk] Proxy evidence may create false activity for broad themes. -> Mitigation: require confidence tiers, source breadth, and no promotion from low-confidence evidence.
- [Risk] Automatic alias or proxy persistence may pollute future runs. -> Mitigation: persist provenance and confidence, and keep related/proxy relationships separate from exact aliases.
- [Risk] Group validation may become too permissive. -> Mitigation: require multiple fresh confirmed members or a combination of fresh proxy-backed activity and multi-source evidence.
- [Risk] Rewriting final labels after validation may make the narrative mention a stronger raw stage than the structured label. -> Mitigation: diagnostics may retain raw labels, but report sections and final judgement should be generated or adjusted to explain the final validated stage.
- [Risk] Preparation can slow batch updates. -> Mitigation: run preparation once per date/window and cache per-entity diagnostics for the batch.
- [Risk] Users may not notice automatic changes. -> Mitigation: CLI output and persisted evidence diagnostics must summarize prepared aliases, proxy candidates, repaired watch rows, and ignored low-confidence matches.

## Migration Plan

1. Add preparation data structures and diagnostics without changing existing report generation behavior.
2. Add market evidence role classification and tests.
3. Wire automatic preparation into init/add/update paths behind defaults and retain skip/debug controls.
4. Update sector and group validation inputs to consume evidence roles and member evidence quality.
5. Synchronize Markdown report labels, database labels, and CLI output after service validation.
6. Regenerate affected historical reports only when users rerun update commands with force.

## Open Questions

- Should proxy relationships be persisted in existing JSON metadata or a dedicated table?
- Which proxy confidence threshold should allow `proxy_market` to satisfy validation gates?
- Should medium-confidence proxy candidates appear in theme suggestions for user review after automatic use as weak evidence?
