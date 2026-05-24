## 1. Pre-Change Analysis

- [x] 1.1 Run GitNexus impact analysis for the `cls_data` command group before editing.
- [x] 1.2 Review existing CLS CLI tests and service query helpers for reuse.

## 2. Export Query Helpers

- [x] 2.1 Implement date-window helper for local calendar day start/end timestamps.
- [x] 2.2 Implement output path helper for `all`, `telegraphs`, and `watch` export types.
- [x] 2.3 Implement local-date discovery for `--all` from telegraph/watch tables.
- [x] 2.4 Query telegraphs for a date when type includes telegraphs.
- [x] 2.5 Query watch data for a date when type includes watch.
- [x] 2.6 Safely parse watch `stocks` and `sectors` JSON values.

## 3. HTML Rendering

- [x] 3.1 Implement `build_cls_export_html()` or equivalent daily document builder.
- [x] 3.2 Render document head with charset, viewport, title, and embedded CSS.
- [x] 3.3 Render overview counts and generated timestamp.
- [x] 3.4 Render telegraph section with time, level badge, title, and content.
- [x] 3.5 Render watch section with time, data type, title, content, stocks, and sectors.
- [x] 3.6 Escape all stored text fields and preserve line breaks safely.
- [x] 3.7 Render no-section placeholders only when a selected type has no records but another selected type has data.

## 4. CLI Command

- [x] 4.1 Add `wchat cls export` command under the existing `cls` group.
- [x] 4.2 Add `--date`, `--all`, `--type`, `--output`, and `--force` options.
- [x] 4.3 Validate `--date` and `--all` are mutually exclusive.
- [x] 4.4 Validate `--output` is not accepted with `--all`.
- [x] 4.5 Default to current local date and type `all`.
- [x] 4.6 Ensure export reads local database only and does not trigger remote fetch.

## 5. Incrementality and Output

- [x] 5.1 Skip existing target files by default.
- [x] 5.2 Overwrite existing target files when `--force` is provided.
- [x] 5.3 Do not generate empty HTML files when the selected scope has no matching data.
- [x] 5.4 Print clear single-date start and completion output.
- [x] 5.5 Print clear all-date batch progress and aggregate summary output.

## 6. Tests

- [x] 6.1 Add CLI tests for default current-date export.
- [x] 6.2 Add CLI tests for specified date export.
- [x] 6.3 Add CLI tests for `--all` daily file generation.
- [x] 6.4 Add CLI tests for `--type telegraphs`, `--type watch`, and `--type all`.
- [x] 6.5 Add tests for existing-file skip and `--force` overwrite.
- [x] 6.6 Add validation tests for invalid option combinations.
- [x] 6.7 Add HTML rendering tests for escaping, badges, stocks, sectors, and no-data behavior.

## 7. Verification

- [x] 7.1 Run focused CLS CLI/export tests.
- [x] 7.2 Run OpenSpec status or validation checks for `export-cls-daily-html`.
- [x] 7.3 Run `gitnexus_detect_changes()` before committing to confirm expected affected symbols and flows.
