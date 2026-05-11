## Why

`wchat fetch --all` currently refreshes batch progress by calendar day. This causes weekend, holiday, and pre-open reruns to create a fresh batch even though they still belong to the same market information cycle, leading to repeated subscription fetches and unnecessary API quota consumption.

## What Changes

- Change batch progress lookup/reset from calendar-date semantics to A-share trade-day semantics.
- Use the market-news boundary rule: before 09:15 on a trade day, `fetch --all` still belongs to the previous trade day; after 09:15 it belongs to the current trade day.
- Keep weekend and holiday reruns attached to the latest previous trade day, so completed subscriptions remain skipped until the next effective trade-day boundary.
- Make `--force` reset the current effective trade-day batch rather than the current calendar-day batch.
- Update user-facing completion/log wording away from "today" where it would be misleading.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `article-fetcher`: Batch resume progress for `fetch_all()` will be keyed by the effective A-share trade day instead of the calendar day.

## Impact

- Affected service code: `src/services/fetcher.py` batch progress helpers and `fetch_all()` messages.
- Affected shared date logic: introduce or reuse a lightweight trade-day helper so fetch progress does not depend on market-summary service construction.
- Affected CLI output: `wchat fetch --all` completion text should describe the effective trade day.
- Affected tests: batch creation, pending lookup, done marking, force reset, weekend/holiday/pre-09:15 boundary cases.
- Database schema impact: no required schema migration if the existing `fetch_batches.batch_date` column is reinterpreted as the effective trade date for new records.
