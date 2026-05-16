## 1. Data Model and Persistence

- [ ] 1.1 Add tracked sector persistence model for canonical name, aliases, source codes, status, discovery metadata, and timestamps
- [ ] 1.2 Add sector trend summary persistence model for sector identity, end date, window days, structured labels, judgement, evidence JSON, content, and output path
- [ ] 1.3 Add database initialization/migration support for the new sector trend tables
- [ ] 1.4 Implement path-safe sector output path generation while preserving display names in persisted metadata

## 2. Sector Identity and Discovery

- [ ] 2.1 Implement sector name normalization for canonical names, including suffix cleanup and stable comparison keys
- [ ] 2.2 Implement conservative deduplication by stable code, canonical name, and explicit aliases
- [ ] 2.3 Implement candidate discovery from cached `MarketSector` rows over a configurable recent window
- [ ] 2.4 Implement candidate discovery from current `FinanceClient.get_sector_data()` results when online mode is available
- [ ] 2.5 Implement candidate discovery from CLS watch sector tags and available local article/news signals
- [ ] 2.6 Implement possible-match surfacing for semantically or textually similar sectors without auto-merging them

## 3. Sector Trend Service

- [ ] 3.1 Add `SectorTrendAnalyzer` or equivalent service with `discover_sectors()`, `list_sectors()`, `init_sector()`, `update_sector_trend()`, `update_all_sector_trends()`, `show_latest()`, and `history()` responsibilities
- [ ] 3.2 Implement sector evidence collection for one sector, including recent strength/weakness appearances, watch signals, telegraph/news/article signals, and related stock signals where available
- [ ] 3.3 Implement previous-summary lookup so single-sector updates can compare against the latest saved trend state
- [ ] 3.4 Implement sparse-evidence handling that marks gaps and prevents strong directional judgements when evidence is insufficient
- [ ] 3.5 Implement batch update selection for `tracked` sectors, including `--limit`, skip-existing behavior, `--force`, and `--continue-on-error`
- [ ] 3.6 Implement optional batch run summary output without making it the primary report artifact

## 4. AI Template and Generation

- [ ] 4.1 Add `templates/sector_trend_summary.md` with tracking conclusion, previous-change comparison, recent performance, catalysts, stock linkage, trend judgement, and follow-up conditions
- [ ] 4.2 Add AI processor method for generating a sector trend summary from structured sector evidence and previous summary context
- [ ] 4.3 Enforce structured output labels for `trend_status`, `strength_level`, and `action_bias`
- [ ] 4.4 Ensure first-time sector updates use an initial-tracking form instead of requiring previous-state comparison

## 5. CLI Commands

- [ ] 5.1 Add and register `wchat ai sector-trends` command group
- [ ] 5.2 Implement `sector-trends discover --days N` for candidate refresh without AI generation
- [ ] 5.3 Implement `sector-trends ls` with status, source, active-window, and limit filters
- [ ] 5.4 Implement `sector-trends init --sector <name>` including promotion from candidate and manual tracked-sector creation
- [ ] 5.5 Implement `sector-trends update --sector <name>` including auto-initialization and report persistence
- [ ] 5.6 Implement `sector-trends update --all` with per-sector progress, tracked-only default selection, failure handling, and summary counts
- [ ] 5.7 Implement `sector-trends show --sector <name>` and `sector-trends history --sector <name>`

## 6. Tests

- [ ] 6.1 Add CLI registration and help tests for `sector-trends` and its subcommands
- [ ] 6.2 Add sector normalization and deduplication tests for code match, canonical-name match, alias match, and related-but-distinct sectors
- [ ] 6.3 Add discovery tests for market cache, current sector data, CLS watch tags, and article/news signals
- [ ] 6.4 Add init tests for candidate promotion and manual tracked-sector creation
- [ ] 6.5 Add single-sector update tests for first update, previous-summary comparison, sparse evidence, and sector-first output path
- [ ] 6.6 Add batch update tests for tracked-only selection, limit handling, skipped records, continue-on-error, and per-sector output isolation
- [ ] 6.7 Add AI prompt/template structure tests for required sections and structured labels

## 7. Verification

- [ ] 7.1 Run targeted unit tests for sector trend identity, discovery, service, CLI, and AI template behavior
- [ ] 7.2 Run existing market-summary tests to verify the new command does not change `wchat ai market-summary`
- [ ] 7.3 Run OpenSpec validation/status checks for `add-sector-trends-tracking`
- [ ] 7.4 Run GitNexus change detection before committing implementation changes
