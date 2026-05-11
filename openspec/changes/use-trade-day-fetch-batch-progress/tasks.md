## 1. Trade-Day Helper

- [ ] 1.1 Add a lightweight trade-day helper for A-share workday detection, previous-trade-day lookup, and effective fetch trade-date calculation
- [ ] 1.2 Cover weekend, holiday, trade-day before 09:15, and trade-day at or after 09:15 helper behavior with tests
- [ ] 1.3 Optionally refactor `MarketAnalyzer` to share the helper where this reduces duplication without changing existing public behavior

## 2. Fetch Batch Progress

- [ ] 2.1 Refactor `FetcherService` batch helpers to compute one effective trade date per `fetch_all()` invocation and pass it through creation, pending lookup, done marking, and reset operations
- [ ] 2.2 Update cleanup cutoff to use the effective trade date as the retention anchor
- [ ] 2.3 Ensure `RateLimitError` and `AuthExpiredError` continue leaving the current effective-trade-day feed as `pending`
- [ ] 2.4 Ensure `wchat fetch --all --force` resets only the effective trade-day batch

## 3. CLI And Messaging

- [ ] 3.1 Update service logs and CLI completion messages to identify the effective trade date instead of saying "today"
- [ ] 3.2 Preserve existing progress event behavior and subscription ordering while changing only the batch key semantics

## 4. Verification

- [ ] 4.1 Update existing fetch batch tests that assert `date.today()` to assert effective trade-date behavior
- [ ] 4.2 Add tests proving weekend and holiday reruns skip feeds already `done` for the previous trade day
- [ ] 4.3 Add tests proving pre-09:15 trade-day reruns keep the previous trade-day batch and post-09:15 runs use the current trade-day batch
- [ ] 4.4 Run targeted fetch batch and trade-day tests
- [ ] 4.5 Run OpenSpec validation for `use-trade-day-fetch-batch-progress`
