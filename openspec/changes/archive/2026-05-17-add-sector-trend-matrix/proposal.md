## Why

Sector and group trend reports are currently stored as individual Markdown files and structured summary rows. Users need a compact trend matrix to compare stage changes across sectors, groups, and dates without opening each report or reading recommendation-oriented text.

The completed trend-stage taxonomy makes `trend_status` stable enough to display as a time-series view. This change adds a read-only trend matrix focused on descriptive stage and strength changes, not trading advice.

## What Changes

- Add a trend matrix view under the existing `wchat ai sector-trends` command group.
- Provide latest snapshot, date-range history, and group-expanded matrix views.
- Display `trend_status` and `strength_level` by date for sectors and groups.
- Compute descriptive change states such as `新增`, `升温`, `延续`, `降温`, `转弱`, and `缺失`.
- Use persisted summary tables as the source of truth and keep Markdown reports as linked detail paths.
- Support Markdown export for matrix reports under `output/trend_matrices/`.
- Hide `action_bias` by default so the view remains a trend-state table rather than a recommendation view.
- No database schema migration is required.

## Capabilities

### New Capabilities

### Modified Capabilities

- `sector-trend-tracking`: Add matrix views for latest and historical sector trend states.
- `sector-group-tracking`: Add matrix views for group trend states and group-member expanded trend states.

## Impact

- Adds read-only service logic for assembling trend matrix rows from `SectorTrendSummary`, `SectorGroupTrendSummary`, `TrackedSector`, `SectorGroup`, and `SectorGroupMember`.
- Adds CLI commands/options under `wchat ai sector-trends`.
- Adds Markdown export files under `output/trend_matrices/`.
- Adds tests for matrix assembly, change-state calculation, group expansion, missing-date handling, and export rendering.
- Does not change AI generation, report storage paths, stage taxonomy, or existing history/show commands.
