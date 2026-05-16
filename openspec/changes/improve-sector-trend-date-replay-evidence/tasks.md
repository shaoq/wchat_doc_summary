## 1. Replay Context Correctness

- [x] 1.1 Add date-bounded previous-summary lookup that can return the latest summary before a target report date.
- [x] 1.2 Update single-sector trend generation to pass the target report date into previous-summary lookup.
- [x] 1.3 Update batch sector trend generation to use the same date-bounded previous-summary semantics for every sector.
- [x] 1.4 Add tests proving historical replay does not use future summaries as prior context.
- [x] 1.5 Add tests proving historical replay uses the nearest earlier summary when one exists.

## 2. CLS Watch Sector Attribution Repair

- [x] 2.1 Add a repair service for CLS watch rows with empty or missing structured `sectors`.
- [x] 2.2 Preserve existing non-empty structured sectors during repair.
- [x] 2.3 Match empty-sector watch rows against tracked sector names, aliases, and normalized comparison keys.
- [x] 2.4 Integrate theme dictionary and accepted learned terms as attribution signals.
- [x] 2.5 Add title/content keyword matching with confidence classification and matched-term diagnostics.
- [x] 2.6 Add stock-based attribution when usable local stock-to-sector evidence is available.
- [x] 2.7 Ensure low-confidence matches remain distinguishable from original structured sector tags.
- [x] 2.8 Add tests for exact matches, alias matches, theme matches, low-confidence matches, unmatched rows, and preservation of existing sectors.

## 3. Update Command Integration

- [x] 3.1 Compute the evidence window for `sector-trends update --date ... --days N` before trend generation.
- [x] 3.2 Run one CLS watch repair pass for the evidence window before batch `update --all` evidence collection.
- [x] 3.3 Run CLS watch repair before single-sector date-specific evidence collection.
- [x] 3.4 Add an explicit skip-repair option for date-specific updates.
- [x] 3.5 Ensure update does not implicitly fetch missing remote CLS watch or market-sector data.
- [x] 3.6 Add CLI tests for batch date update, single-sector date update, and skip-repair mode.

## 4. Standalone Repair CLI

- [x] 4.1 Add a standalone `sector-trends` command for repairing CLS watch sector attribution by date/window.
- [x] 4.2 Render repair results with repaired, unchanged, unmatched, skipped, and low-confidence counts.
- [x] 4.3 Ensure the standalone repair command does not generate sector trend Markdown files.
- [x] 4.4 Ensure the standalone repair command does not create or update sector trend summary rows.
- [x] 4.5 Add CLI tests for standalone repair output and no-report side effects.

## 5. Evidence Diagnostics

- [x] 5.1 Extend collected sector evidence diagnostics with market, CLS watch, CLS telegraph, total evidence, and data-gap counts.
- [x] 5.2 Include repair diagnostics in update results when automatic repair runs.
- [x] 5.3 Persist evidence diagnostics in `evidence_json` for later history, matrix, and debugging views.
- [x] 5.4 Ensure diagnostics distinguish missing structured data from no-direction/no-trend judgement.
- [x] 5.5 Add tests for persisted diagnostics in sparse, repaired, and unrepaired evidence scenarios.

## 6. Validation and Regression Coverage

- [x] 6.1 Add tests proving conservative `validate_sector_stage()` behavior is unchanged by repair.
- [x] 6.2 Add tests proving repaired low-confidence watch evidence alone does not promote strong stages.
- [x] 6.3 Add tests proving repaired multi-source evidence can support stages already allowed by the taxonomy.
- [x] 6.4 Run targeted sector trend, date replay, repair, and taxonomy tests.
- [x] 6.5 Run `openspec validate improve-sector-trend-date-replay-evidence --strict`.
