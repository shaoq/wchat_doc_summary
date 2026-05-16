## 1. Data Model and Persistence

- [x] 1.1 Add tracked sector persistence model for canonical name, aliases, source codes, status, discovery metadata, and timestamps
- [x] 1.2 Add sector trend summary persistence model for sector identity, end date, window days, structured labels, judgement, evidence JSON, content, and output path
- [x] 1.3 Add database initialization/migration support for the new sector trend tables
- [x] 1.4 Implement path-safe sector output path generation while preserving display names in persisted metadata

## 2. Sector Identity and Discovery

- [x] 2.1 Implement sector name normalization for canonical names, including suffix cleanup and stable comparison keys
- [x] 2.2 Implement conservative deduplication by stable code, canonical name, and explicit aliases
- [x] 2.3 Implement candidate discovery from cached `MarketSector` rows over a configurable recent window
- [x] 2.4 Implement candidate discovery from current `FinanceClient.get_sector_data()` results when online mode is available
- [x] 2.5 Implement candidate discovery from CLS watch sector tags and available local article/news signals
- [x] 2.6 Implement possible-match surfacing for semantically or textually similar sectors without auto-merging them

## 3. Sector Trend Service

- [x] 3.1 Add `SectorTrendAnalyzer` or equivalent service with `discover_sectors()`, `list_sectors()`, `init_sector()`, `update_sector_trend()`, `update_all_sector_trends()`, `show_latest()`, and `history()` responsibilities
- [x] 3.2 Implement sector evidence collection for one sector, including recent strength/weakness appearances, watch signals, telegraph/news/article signals, and related stock signals where available
- [x] 3.3 Implement previous-summary lookup so single-sector updates can compare against the latest saved trend state
- [x] 3.4 Implement sparse-evidence handling that marks gaps and prevents strong directional judgements when evidence is insufficient
- [x] 3.5 Implement batch update selection for `tracked` sectors, including `--limit`, skip-existing behavior, `--force`, and `--continue-on-error`
- [x] 3.6 Implement optional batch run summary output without making it the primary report artifact

## 4. AI Template and Generation

- [x] 4.1 Add `templates/sector_trend_summary.md` with tracking conclusion, previous-change comparison, recent performance, catalysts, stock linkage, trend judgement, and follow-up conditions
- [x] 4.2 Add AI processor method for generating a sector trend summary from structured sector evidence and previous summary context
- [x] 4.3 Enforce structured output labels for `trend_status`, `strength_level`, and `action_bias`
- [x] 4.4 Ensure first-time sector updates use an initial-tracking form instead of requiring previous-state comparison

## 5. CLI Commands

- [x] 5.1 Add and register `wchat ai sector-trends` command group
- [x] 5.2 Implement `sector-trends discover --days N` for candidate refresh without AI generation
- [x] 5.3 Implement `sector-trends ls` with status, source, active-window, and limit filters
- [x] 5.4 Implement `sector-trends init --sector <name>` including promotion from candidate and manual tracked-sector creation
- [x] 5.5 Implement `sector-trends update --sector <name>` including auto-initialization and report persistence
- [x] 5.6 Implement `sector-trends update --all` with per-sector progress, tracked-only default selection, failure handling, and summary counts
- [x] 5.7 Implement `sector-trends show --sector <name>` and `sector-trends history --sector <name>`

## 6. Tests

- [x] 6.1 Add CLI registration and help tests for `sector-trends` and its subcommands
- [x] 6.2 Add sector normalization and deduplication tests for code match, canonical-name match, alias match, and related-but-distinct sectors
- [x] 6.3 Add discovery tests for market cache, current sector data, CLS watch tags, and article/news signals
- [x] 6.4 Add init tests for candidate promotion and manual tracked-sector creation
- [x] 6.5 Add single-sector update tests for first update, previous-summary comparison, sparse evidence, and sector-first output path
- [x] 6.6 Add batch update tests for tracked-only selection, limit handling, skipped records, continue-on-error, and per-sector output isolation
- [x] 6.7 Add AI prompt/template structure tests for required sections and structured labels

## 7. Verification

- [x] 7.1 Run targeted unit tests for sector trend identity, discovery, service, CLI, and AI template behavior
- [x] 7.2 Run existing market-summary tests to verify the new command does not change `wchat ai market-summary`
- [x] 7.3 Run OpenSpec validation/status checks for `add-sector-trends-tracking`
- [x] 7.4 Run GitNexus change detection before committing implementation changes
