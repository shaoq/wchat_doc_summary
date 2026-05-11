## Context

`wchat fetch --all` uses `fetch_batches` to resume batch fetches after interruption. The current implementation keys records by `date.today()`, and the archived batch-resume spec explicitly describes `batch_date` as a calendar date.

That works for ordinary same-day retries, but it is misaligned with the market-news workflow. Articles published after close and before the next market open are still part of the previous trading cycle. A weekend, holiday, or pre-09:15 rerun should continue the same effective trade-day batch instead of starting a fresh calendar-day batch.

The project already has A-share trade-day logic in `MarketAnalyzer`, but `FetcherService` should not directly construct or depend on `MarketAnalyzer` because that service also owns market-summary, finance-client, and cache responsibilities unrelated to article fetching.

## Goals / Non-Goals

**Goals:**

- Key `fetch_all()` batch creation, pending lookup, done marking, and force reset by effective A-share trade day.
- Define the effective trade-day boundary as 09:15 local time: before 09:15 on a trade day, use the previous trade day; at or after 09:15, use the current trade day.
- Preserve weekend and holiday retries under the latest previous trade-day batch.
- Keep the existing `fetch_batches` table usable without a schema migration.
- Update tests and user-facing wording so behavior no longer promises calendar-day reset.

**Non-Goals:**

- Do not change single-subscription `wchat fetch <mp_id>` behavior.
- Do not change article fetch range semantics for `--days`, `--full`, or default latest-count fetches.
- Do not implement a full exchange calendar beyond the project's existing conservative A-share rule.
- Do not backfill or rewrite old calendar-day batch rows.
- Do not change rate-limit, auth-expired, or provider selection behavior.

## Decisions

### D1: Effective Trade Day Helper

Create a lightweight trade-day helper, for example `src/services/trade_calendar.py`, with pure functions for:

- `is_trade_day(check_date)`
- `get_previous_trade_date(trade_date)`
- `get_effective_fetch_trade_date(now=None)`

`MarketAnalyzer` can continue to own its current public methods during the initial implementation, but duplicated calendar logic should be minimized. A helper avoids making article fetching depend on market-summary service construction.

Alternative considered: instantiate `MarketAnalyzer` inside `FetcherService`. This would reuse existing methods quickly, but it couples article fetch batch progress to finance and cache dependencies that are unrelated to fetching subscriptions.

### D2: 09:15 Boundary

Use 09:15 local time as the trade-day switch boundary for batch progress.

Rationale: market-summary article windows already treat post-close articles as belonging to the previous trade day until the next trade day 09:15. Aligning fetch progress with that window avoids refreshing the batch before the previous trading cycle is complete.

Alternative considered: reuse `MarketAnalyzer.get_latest_trade_date()` as-is, which switches at 09:00. That is close, but it leaves a 15-minute gap where fetch progress can reset before the article window closes.

### D3: Keep `batch_date` Column, Change Semantics

Keep the existing `fetch_batches.batch_date` column and unique constraint `(mp_id, batch_date)`. New code will treat `batch_date` as the effective fetch trade date.

Rationale: the stored value is still a date and the uniqueness model remains correct. Renaming the column would require a migration with limited practical benefit.

Alternative considered: add a new `batch_trade_date` column. This would be explicit but creates migration and compatibility work without changing query shape.

### D4: No Backfill for Old Batch Rows

Do not rewrite existing records created under calendar-day semantics. After deployment, new runs will query by effective trade date. Old records for dates that do not match the effective trade date will naturally be ignored and cleaned up by retention.

Rationale: batch records are short-lived and operational, not durable business data.

### D5: Wording

Replace "今日所有订阅已同步完成" and related logs with wording that includes the effective trade date, such as "交易日 2026-05-08 的订阅已同步完成".

Rationale: once weekends and holidays can map to a previous trade date, "today" becomes misleading.

## Risks / Trade-offs

- [Existing weekend batch rows become ignored] -> Acceptable because batch rows are short-lived; users can rerun or use `--force` if needed.
- [Trade-day helper duplicates `MarketAnalyzer` behavior] -> Keep helper narrow and covered by tests; optionally refactor `MarketAnalyzer` to delegate to it during implementation.
- [09:15 boundary surprises users who expect calendar-day refresh] -> CLI/log wording will expose the effective trade date.
- [Holiday calendar accuracy depends on `chinese_calendar`] -> This matches existing project behavior and avoids introducing a new dependency.
