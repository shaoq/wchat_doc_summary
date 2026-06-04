## 1. Pre-Change Analysis

- [x] 1.1 Run GitNexus impact analysis for `Feed` before editing the model.
- [x] 1.2 Run GitNexus impact analysis for the `export` CLI symbol before changing command structure.
- [x] 1.3 Review existing `wchat export`, `wchat ls`, `wchat info`, and `set_weight` tests to preserve current behavior.

## 2. Data Model and Compatibility

- [x] 2.1 Add a boolean-like `include_in_export_all` field to the `Feed` model with default enabled.
- [x] 2.2 Extend database compatibility schema handling to add the `feeds.include_in_export_all` column with default enabled for existing SQLite databases.
- [x] 2.3 Ensure new subscriptions and reactivated subscriptions preserve or receive the default enabled preference correctly.

## 3. Subscription Display and Preference Update

- [x] 3.1 Add service or CLI update logic to set `include_in_export_all` for an existing subscription.
- [x] 3.2 Add `wchat export set-export <MP_ID> true|false` and clear success/not-found output.
- [x] 3.3 Convert or wrap the existing `export` command so current usages still work alongside the `set-export` subcommand.
- [x] 3.4 Add a "批量导出" column to `wchat ls`.
- [x] 3.5 Add batch export preference output to `wchat info <MP_ID>`.

## 4. Export Behavior

- [x] 4.1 Update `wchat export --all` feed selection to include only active feeds with batch export enabled.
- [x] 4.2 Preserve `wchat export <MP_ID>` and `wchat export <MP_ID> --force` behavior for feeds with batch export disabled.
- [x] 4.3 Add a distinct message for active subscriptions existing but none enabled for batch export.
- [x] 4.4 Ensure `wchat export --all --force` does not rebuild directories for disabled feeds.

## 5. Tests

- [x] 5.1 Add model/database compatibility tests proving existing feeds default to batch export enabled.
- [x] 5.2 Add CLI tests for `wchat export set-export` true, false, and unknown subscription cases.
- [x] 5.3 Add CLI tests proving `wchat ls` and `wchat info` display the batch export preference.
- [x] 5.4 Add export-all tests proving enabled feeds export and disabled feeds are skipped.
- [x] 5.5 Add export tests proving explicit single-feed export still works when batch export is disabled.
- [x] 5.6 Add export-all force tests proving disabled feed directories are not rebuilt.
- [x] 5.7 Add compatibility tests proving existing `wchat export <MP_ID>`, `wchat export --all`, and validation behavior remain intact after command-group changes.

## 6. Verification

- [x] 6.1 Run focused subscription and export CLI tests.
- [x] 6.2 Run OpenSpec validation/status checks for `add-export-all-preference`.
- [x] 6.3 Run `gitnexus_detect_changes()` before committing to confirm affected symbols and flows match the expected scope.
