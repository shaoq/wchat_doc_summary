## Context

Sector trend updates currently collect evidence from `market_sectors`, structured `cls_watch_data.sectors`, and `cls_telegraphs`. The generated reports are then validated by the trend-stage taxonomy, which intentionally downgrades sparse or weak evidence to conservative stages.

Recent historical replay exposed two data-quality issues:

- CLS watch rows exist for the replay windows, but many rows have empty structured `sectors`, so watch evidence is invisible to sector trend collection.
- Date-specific replay may use a report after the target date as `previous_summary`, which contaminates "compared with previous update" narratives and prior-stage validation.

The current conservative taxonomy should remain intact. This change improves the evidence and replay context supplied to the existing generation and validation flow.

## Goals / Non-Goals

**Goals:**

- Ensure date-specific sector updates only use previous-summary context before the target report date.
- Backfill structured CLS watch sector attribution from local raw watch content before collecting evidence for date-specific updates.
- Make batch and single-sector date replay behave consistently.
- Keep attribution auditable with match source, confidence, and matched terms where storage permits.
- Expose diagnostics that explain whether a no-trend result is caused by missing evidence, weak evidence, or no directional evidence.
- Preserve conservative trend-stage validation rules.

**Non-Goals:**

- Do not relax `validate_sector_stage()` or broaden stage labels in this change.
- Do not fetch missing remote CLS watch or market-sector data implicitly during `sector-trends update`.
- Do not automatically merge related but distinct sectors such as `光伏` and `TOPCon`.
- Do not rewrite existing historical reports unless the user reruns update or repair commands.
- Do not require trend matrix implementation.

## Decisions

### 1. Repair Structured Watch Attribution Before Evidence Collection

For `sector-trends update --date`, the command should compute the evidence window and run a CLS watch attribution repair for existing watch rows in that window before sector evidence collection.

Rationale: trend generation should consume stable structured evidence rather than doing ad hoc text matching separately for each sector report.

Alternative considered: keep `cls_watch_data.sectors` empty and add title/content fallback inside `collect_sector_evidence()`. This is simpler initially, but it duplicates attribution work across sectors, makes results harder to audit, and prevents group suggestions or future matrix diagnostics from reusing repaired evidence.

### 2. Keep Structure-First Matching With Controlled Text Fallback

The attribution repair should preserve existing non-empty `sectors` as the highest-priority source. Empty or incomplete rows can be enriched from local signals:

- exact tracked-sector name and explicit alias matches
- theme dictionary terms and accepted learned terms
- title/content keyword matches
- watch item stocks where usable local stock-to-sector evidence exists
- cross-signal confirmation from multiple match sources

Each inferred sector should carry attribution metadata such as match source, confidence, and matched terms. If schema changes are avoided, metadata can be stored in a sidecar JSON field/table or emitted through repair diagnostics, but `sectors` should still be populated for existing evidence consumers.

Rationale: structure-first matching avoids degrading curated upstream sectors, while controlled fallback turns otherwise invisible watch rows into usable but confidence-aware evidence.

Alternative considered: blindly write all keyword hits into `sectors`. This risks over-attribution and can create false trends.

### 3. Do Not Implicitly Refresh Missing Raw Data

The repair step should operate on existing local rows only. If `cls_watch_data` or `market_sectors` lacks raw data for a date, update diagnostics should report the cache miss rather than triggering network fetches.

Rationale: historical replay should be deterministic and should not unexpectedly mutate unrelated market caches or depend on network availability.

Alternative considered: add automatic data fetch before every replay. This may be useful later behind an explicit option, but it expands scope and failure modes.

### 4. Bound Previous Summary by Report Date

Previous-summary lookup should accept an optional target report date. When present, it should select the latest summary with `end_date < report_date`. Existing non-date-specific behavior can continue to read the latest summary.

Rationale: replaying `2026-05-06` must not compare against `2026-05-15` or use a future active stage to justify an earlier report.

Alternative considered: infer previous context from output file order. Database summary rows are already the source of truth and are less brittle than Markdown paths.

### 5. Add Diagnostics Without Changing Stage Semantics

Evidence collection should expose diagnostics such as data gaps, repair counts, source counts, inferred watch matches, and low-confidence attribution counts. Reports and CLI output can use these diagnostics to explain conservative labels.

Rationale: `暂无趋势` currently conflates "no directional trend" with "insufficient structured data." Diagnostics make the distinction visible while keeping the persisted `trend_status` enum stable.

Alternative considered: add new trend statuses such as `数据不足`. That would affect taxonomy, matrix ranking, and existing tests; it is unnecessary for this change.

## Risks / Trade-offs

- [Risk] Text-based attribution may create false sector hits. -> Mitigation: use confidence metadata, exact/alias/theme dictionaries, and avoid treating low-confidence matches as strong evidence.
- [Risk] Repairing `sectors` mutates historical watch rows. -> Mitigation: preserve original non-empty sectors, keep attribution provenance, and provide a dry-run or diagnostics mode for standalone repair if practical.
- [Risk] Additional repair work slows batch replay. -> Mitigation: run repair once per evidence window before the batch, not once per sector.
- [Risk] Existing reports remain inconsistent until regenerated. -> Mitigation: document that repair affects subsequent updates and standalone repair only updates structured watch attribution, not existing reports.
- [Risk] Sidecar attribution storage may add schema complexity. -> Mitigation: prefer minimal compatible storage; if a migration is needed, keep existing `sectors` consumers compatible.

## Migration Plan

1. Add attribution repair service and tests against existing `cls_watch_data` rows with empty sectors.
2. Add date-bounded previous-summary lookup and update single/batch sector update paths to use it.
3. Wire date-specific update commands to run one repair pass for the computed evidence window before generation.
4. Add standalone repair CLI for existing data backfill and diagnostics.
5. Rerun targeted historical replay tests; existing reports are only replaced when users rerun update with `--force`.

Rollback is straightforward: disable automatic repair with the skip option and keep reading existing structured `sectors`. Date-bounded previous-summary lookup should remain because it fixes replay correctness.

## Open Questions

- Should attribution provenance live in a new sidecar table, a JSON column, or only command diagnostics for the first implementation?
- Should automatic repair run for non-date-specific latest updates, or only when `--date` is supplied?
- What confidence threshold should be required before an inferred watch sector contributes to `has_multi_signal_fresh`?
