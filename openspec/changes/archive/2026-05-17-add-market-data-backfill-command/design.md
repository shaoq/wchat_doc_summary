## Context

`wchat ai market-summary --date` currently treats historical trade dates as cache replay only. That protects summaries from accidentally using current realtime snapshots for old dates, but it also means missing historical `MarketSector` rows cannot be recovered through the summary command.

Sector trend reports read recent evidence from `MarketSector` and `CLSWatchData`; group trend reports then read member `SectorTrendSummary` rows. CLS watch and telegraph commands already support time-window backfill, but market-data cache backfill is missing and trend updates always target the latest trade date.

## Goals / Non-Goals

**Goals:**
- Add an explicit `wchat ai market-data backfill --date <YYYY-MM-DD>` command for historical market-data cache population.
- Prevent realtime snapshot sources from being written under historical trade dates.
- Keep historical `market-summary` behavior as cache replay, not backfill.
- Support explicit-date sector and group trend replay after data backfill.
- Surface sparse evidence clearly so trend/group reports do not overstate confidence.

**Non-Goals:**
- Replacing all finance data providers.
- Guaranteeing every historical field is available for every date.
- Changing CLS `fetch-watch` or `fetch-telegraphs` as the primary path for CLS historical ingestion.
- Auto-generating full market summaries for every backfilled date.

## Decisions

1. Introduce a dedicated backfill command group.

   `wchat ai market-data backfill --date <date>` will populate cache tables only. It will not call the LLM and will not save `market_summaries`.

   Alternative considered: extend `market-summary --force` to fetch historical data. Rejected because summary generation mixes market data, CLS data, articles, overseas context, and LLM output; using it as a backfill tool makes partial failures hard to reason about.

2. Use source capability metadata for historical safety.

   Finance data adapters should declare whether they are safe for a specific historical date. Backfill may write rows only from date-specific sources. Realtime snapshot sources must return `skipped_unsupported` for historical dates instead of writing current data into old cache keys.

   Alternative considered: trust each provider method to handle historical dates correctly. Rejected because current `get_all_market_data(trade_date=...)` passes `trade_date` only to some categories while sectors, indices, and statistics still use current snapshot style sources.

3. Backfill should be category-aware and partial-success friendly.

   A run can populate supported categories and report unsupported or empty categories without failing the whole command. The cache remains useful when only limit-up, turnover, or other date-safe subsets are available.

   Alternative considered: all-or-nothing backfill. Rejected because historical data sources have uneven availability and a strict failure model would block useful partial evidence.

4. Keep historical summary cache replay unchanged.

   `market-summary --date <historical>` should continue to call `collect_market_data()` in cache-only mode. Users who want missing cache rows must run the new backfill command first.

   Alternative considered: make market-summary auto-backfill when cache is missing. Rejected because it hides network writes behind a generation command and makes historical summaries less reproducible.

5. Add explicit-date trend replay.

   `sector-trends update` and `sector-trends groups update` should accept a target date and use that date for evidence windows, freshness checks, output paths, and idempotency checks. Group reports should use member reports for the same target date when available and mark missing/stale members explicitly.

   Alternative considered: rely on latest-date reports only. Rejected because historical backfill is only useful for trend formation if reports can be generated for the same date sequence.

## Risks / Trade-offs

- Historical provider coverage may be incomplete -> report per-source statuses and write only validated categories.
- Some source APIs may return current data despite accepting a date parameter -> require tests that verify provider methods pass the date through and never write unsupported snapshot results for historical dates.
- Partial backfill may still leave trend evidence sparse -> trend and group report generation must expose data gaps and downgrade judgement.
- Adding explicit-date trend replay increases command surface -> keep defaults unchanged so existing latest-date workflows continue to work.

## Migration Plan

1. Add the new backfill service and CLI command without changing existing `market-summary` defaults.
2. Add source capability metadata and tests around historical-safe categories.
3. Add explicit-date options to sector and group trend commands.
4. Document the recommended workflow: backfill market data, fetch CLS data, then replay sector and group trend reports by date.
5. Rollback is straightforward: remove the new command and explicit-date options; existing cache tables and latest-date behavior remain compatible.

## Open Questions

- Which finance categories should be enabled in the first implementation based on verified historical provider support?
- Should the first version support date ranges, or only a single `--date` plus shell loops?
- Should backfill optionally trigger CLS fetch commands, or remain market-data-only as the command name implies?
