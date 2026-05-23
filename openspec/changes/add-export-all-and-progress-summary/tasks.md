## 1. Pre-Change Analysis

- [x] 1.1 Run GitNexus impact analysis for the export command and helper symbols before editing.
- [x] 1.2 Review the completed `export-articles-as-html` implementation and reuse its HTML builder and filename behavior.

## 2. Export Core Refactor

- [x] 2.1 Introduce an export summary structure with feed identity, output directory, exported, skipped, failed, and total counts.
- [x] 2.2 Extract reusable single-feed export logic shared by targeted export and `--all`.
- [x] 2.3 Keep per-article incremental skip behavior based on existing `.html` files.
- [x] 2.4 Catch per-article write failures, increment failed count, and continue where possible.
- [x] 2.5 Ensure `--force` clears only the current feed export directory before exporting that feed.

## 3. CLI Scope Handling

- [x] 3.1 Make the `MP_ID` argument optional for `wchat export`.
- [x] 3.2 Add a `--all` option.
- [x] 3.3 Reject calls with neither `MP_ID` nor `--all` using a clear usage message.
- [x] 3.4 Reject calls with both `MP_ID` and `--all` using a clear usage message.
- [x] 3.5 Query active feeds deterministically for `--all`.
- [x] 3.6 Handle no active feeds with a clear no-subscriptions message.

## 4. Terminal Output

- [x] 4.1 Add single-account start output showing account name, mp_id, mode, format, and output directory.
- [x] 4.2 Add single-account completion output showing exported, skipped, failed, and total counts.
- [x] 4.3 Add explicit no-new-articles output when incremental export exports zero and skips existing files.
- [x] 4.4 Add all-account batch start output showing account count, mode, and format.
- [x] 4.5 Add per-account progress markers and per-account summaries for `--all`.
- [x] 4.6 Add aggregate summary for `--all` with account count and article totals.
- [x] 4.7 Highlight non-zero failure counts in terminal output.

## 5. Tests

- [x] 5.1 Add CLI tests for `wchat export --all` exporting multiple active feeds.
- [x] 5.2 Add CLI tests for `--all --force` rebuilding per-feed directories.
- [x] 5.3 Add CLI validation tests for missing scope and conflicting `MP_ID` plus `--all`.
- [x] 5.4 Add tests for no active feeds.
- [x] 5.5 Add tests for single-account and all-account terminal summary content.
- [x] 5.6 Add tests for per-article write failure counting and continuation.

## 6. Verification

- [x] 6.1 Run focused export CLI tests.
- [x] 6.2 Run OpenSpec status or validation checks for `add-export-all-and-progress-summary`.
- [x] 6.3 Run `gitnexus_detect_changes()` before committing to confirm expected affected symbols and flows.
