## Why

Current historical market-summary runs only replay cached market data. When a historical trade date has no `MarketSector` cache, `wchat ai market-summary --date ... --force` cannot backfill it, which leaves sector trend and group trend analysis with sparse or misleading historical evidence.

This change introduces an explicit market-data backfill path so historical data collection is separated from summary generation and can enforce source-specific historical safety.

## What Changes

- Add a dedicated `wchat ai market-data backfill --date <YYYY-MM-DD>` command for populating market-data cache rows for a historical trade date.
- Keep `wchat ai market-summary --date ...` semantics conservative: historical summaries continue to use cached market data only and do not silently fetch live replacement data.
- Add source capability checks so only data providers that truly support date-specific historical queries may write historical cache rows.
- Report per-source outcomes for backfill runs, including populated, skipped-unsupported, empty, and failed sources.
- Extend sector trend updates to support explicit report dates so backfilled evidence can be replayed into historical sector trend reports.
- Extend sector group trend updates to support explicit report dates and to rely on date-appropriate member reports.
- Strengthen trend evidence quality by requiring explicit sparse-data handling when market-sector history or member reports are incomplete.

## Capabilities

### New Capabilities
- `market-data-backfill`: Defines explicit historical market-data cache backfill behavior, CLI contract, source eligibility, and reporting.

### Modified Capabilities
- `market-summary`: Clarifies that historical summary generation remains cache-replay-only and must not be used as the backfill mechanism.
- `market-data-cache`: Adds requirements for date-specific historical cache writes and prevention of live snapshot contamination.
- `sector-trend-tracking`: Adds explicit-date trend replay behavior and evidence quality handling for backfilled historical data.
- `sector-group-tracking`: Adds explicit-date group trend replay behavior and member freshness handling for historical reports.

## Impact

- CLI: new `wchat ai market-data` command group with `backfill` subcommand; likely additions to `wchat ai --help`.
- Services: new backfill orchestration service or `MarketAnalyzer`/cache-layer extension for historical-safe provider selection.
- Data sources: `FinanceClient` source methods need capability metadata distinguishing date-specific historical sources from realtime snapshot sources.
- Storage: existing market cache tables are reused; writes must remain upserts by trade date and business key.
- Tests: new CLI, service, and cache tests for historical source eligibility, no live snapshot contamination, and trend replay using explicit dates.
