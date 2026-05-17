## 1. Matrix Service

- [x] 1.1 Add a read-only trend matrix service that queries sector summaries, group summaries, tracked sectors, groups, and memberships.
- [x] 1.2 Implement date selection for latest view and bounded historical windows.
- [x] 1.3 Implement sector matrix row assembly with report paths and missing-cell handling.
- [x] 1.4 Implement group matrix row assembly with member counts and missing-cell handling.
- [x] 1.5 Implement selected-group expansion with group row, member rows, relation types, and sector report cells.

## 2. Change State Calculation

- [x] 2.1 Define sector stage ranking for display-only change-state calculation.
- [x] 2.2 Define group stage ranking for display-only change-state calculation.
- [x] 2.3 Implement change states for `新增`, `升温`, `延续`, `降温`, `转弱`, and `缺失`.
- [x] 2.4 Ensure change-state calculation does not use `action_bias`.

## 3. CLI and Rendering

- [x] 3.1 Add matrix command/options under `wchat ai sector-trends`.
- [x] 3.2 Render latest snapshot as a Rich table.
- [x] 3.3 Render historical sector/group matrices as Rich tables with date columns.
- [x] 3.4 Render selected-group expanded matrices as Rich tables.
- [x] 3.5 Hide `action_bias` by default and keep output descriptive.

## 4. Markdown Export

- [x] 4.1 Add Markdown rendering for latest and historical trend matrices.
- [x] 4.2 Add Markdown rendering for selected-group expanded matrices.
- [x] 4.3 Add default export paths under `output/trend_matrices/`.
- [x] 4.4 Support explicit output path override without overwriting sector or group reports.

## 5. Tests and Verification

- [x] 5.1 Add unit tests for sector matrix assembly and missing cells.
- [x] 5.2 Add unit tests for group matrix assembly and selected-group expansion.
- [x] 5.3 Add unit tests for sector and group change-state calculation.
- [x] 5.4 Add CLI tests for latest, history-window, group-expanded, and Markdown export modes.
- [x] 5.5 Run targeted trend matrix tests and OpenSpec validation.
