## 1. Market Backfill Core

- [x] 1.1 Add source capability metadata for market-data categories, distinguishing historical-safe sources from realtime snapshot sources.
- [x] 1.2 Implement a market-data backfill service that accepts one trade date and returns normalized per-category outcomes.
- [x] 1.3 Ensure historical backfill writes only validated historical-safe data to existing cache tables.
- [x] 1.4 Ensure unsupported, empty, and failed category outcomes preserve existing valid cache rows.
- [x] 1.5 Add unit tests for source eligibility, partial success, idempotent writes, and no historical snapshot contamination.

## 2. Market Data CLI

- [x] 2.1 Add the `wchat ai market-data` command group.
- [x] 2.2 Add `wchat ai market-data backfill --date <YYYY-MM-DD>` with date validation and no LLM execution.
- [x] 2.3 Render per-category backfill outcomes with populated, skipped-unsupported, empty, failed, and partial-completion summaries.
- [x] 2.4 Add CLI tests for help output, invalid date handling, successful partial backfill rendering, and no market-summary creation.

## 3. Market Summary Integration

- [x] 3.1 Preserve historical `market-summary --date` cache-replay-only behavior.
- [x] 3.2 Update historical-missing-cache CLI output to point users to `wchat ai market-data backfill --date <date>`.
- [x] 3.3 Add regression tests proving `market-summary --date ... --force` does not fetch realtime replacement data for historical dates.

## 4. Sector Trend Date Replay

- [x] 4.1 Add explicit report-date support to `SectorTrendAnalyzer.update_sector_trend` and batch update flow while keeping latest-date defaults unchanged.
- [x] 4.2 Add `--date` to `wchat ai sector-trends update` for single-sector and `--all` modes.
- [x] 4.3 Ensure evidence windows end at the requested date and exclude records after that date.
- [x] 4.4 Add explicit market-sector and CLS evidence gap metadata for sparse historical windows.
- [x] 4.5 Include matching stored CLS telegraph mentions in sector evidence and prompt formatting.
- [x] 4.6 Add tests for explicit-date output paths, idempotency checks, evidence window bounds, sparse gaps, and telegraph mention inclusion.

## 5. Sector Group Date Replay

- [x] 5.1 Add explicit report-date support to group update service and batch update flow while keeping latest-date defaults unchanged.
- [x] 5.2 Add `--date` to `wchat ai sector-trends groups update` for single-group and `--all` modes.
- [x] 5.3 Make group evidence prefer member summaries for the target date and reject future summaries for historical replay.
- [x] 5.4 Mark missing or stale target-date member summaries in member freshness and group data gaps.
- [x] 5.5 Add tests for target-date member selection, future-summary exclusion, stale freshness, and sparse group judgement behavior.

## 6. Verification

- [x] 6.1 Run focused tests for market summary, market cache, backfill CLI, sector trends, and sector groups.
- [x] 6.2 Run `openspec validate add-market-data-backfill-command --strict`.
- [x] 6.3 Run GitNexus change detection before commit or handoff.
