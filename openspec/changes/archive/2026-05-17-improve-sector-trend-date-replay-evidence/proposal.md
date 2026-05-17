## Why

Historical sector trend replay currently generates many `暂无趋势` reports because CLS watch records often have empty structured `sectors`, and replayed updates may read a future report as the "previous" summary. This makes date-specific backfills less reliable and weakens downstream trend matrices that depend on comparable persisted labels.

## What Changes

- Repair sector trend date replay so previous-summary context is bounded to reports before the target report date.
- Add a structured CLS watch sector attribution step that fills empty `cls_watch_data.sectors` from existing raw watch title/content/stocks evidence and theme/sector dictionaries.
- Make `sector-trends update --sector/--all --date ...` run the attribution repair for the requested evidence window before collecting sector evidence, unless explicitly skipped.
- Add a standalone repair command for users who want to backfill CLS watch sector attribution without generating trend reports.
- Preserve conservative trend-stage validation; this change improves evidence quality rather than loosening `validate_sector_stage()` rules.
- Surface attribution/evidence diagnostics so users can distinguish true no-trend results from data coverage gaps.

## Capabilities

### New Capabilities

### Modified Capabilities

- `sector-trend-tracking`: Date-specific updates SHALL repair and consume structured CLS watch sector evidence for the requested window, and previous-summary context SHALL be selected relative to the target report date.

## Impact

- Affects `wchat ai sector-trends update` command behavior for date-specific single and batch updates.
- Adds a repair-oriented CLI path under `wchat ai sector-trends`.
- Adds service logic for CLS watch sector attribution using existing local data, theme dictionaries, tracked sectors, aliases, and watch item stocks when available.
- Updates sector evidence collection diagnostics and previous-summary lookup semantics.
- Adds tests for historical replay, attribution repair, skipped repair mode, diagnostics, and preserved conservative stage validation.
- Does not fetch missing remote market/watch data implicitly and does not relax trend-stage taxonomy constraints.
