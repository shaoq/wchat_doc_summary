# market-data-backfill Specification

## Purpose
TBD - created by archiving change add-market-data-backfill-command. Update Purpose after archive.
## Requirements
### Requirement: System SHALL expose an explicit market-data backfill command
The system SHALL provide a `wchat ai market-data backfill` command that populates local market-data cache rows for a requested trade date without generating an AI market summary.

#### Scenario: Backfill command appears in AI command surface
- **WHEN** a user runs `wchat ai market-data --help`
- **THEN** the output SHALL include the `backfill` subcommand
- **AND** the command help SHALL describe `--date` as a required trade-date input in `YYYY-MM-DD` format

#### Scenario: Backfill requires a valid date
- **WHEN** a user runs `wchat ai market-data backfill --date invalid`
- **THEN** the command SHALL reject the input before calling any remote market data provider
- **AND** it SHALL print a date-format error

#### Scenario: Backfill does not generate a summary
- **WHEN** a user runs `wchat ai market-data backfill --date 2026-05-15`
- **THEN** the system SHALL NOT call market-summary LLM generation
- **AND** it SHALL NOT create or update a `market_summaries` row for that date

### Requirement: Backfill SHALL write only historical-safe market data
The backfill workflow SHALL write cache rows for a historical trade date only from sources that are explicitly verified as date-specific historical sources.

#### Scenario: Historical-safe source populates cache
- **WHEN** a source category supports date-specific historical queries
- **AND** that source returns validated data for the requested trade date
- **THEN** backfill SHALL write or update the corresponding cache rows under that requested trade date

#### Scenario: Realtime snapshot source is skipped for historical date
- **WHEN** a source category only supports realtime or current snapshot data
- **AND** the requested date is before the latest trade date
- **THEN** backfill SHALL NOT call that source as a historical source
- **AND** it SHALL report the category as `skipped_unsupported`

#### Scenario: Source returns empty historical data
- **WHEN** a historical-safe source returns no records for the requested date
- **THEN** backfill SHALL leave existing cache rows for that category unchanged
- **AND** it SHALL report the category as `empty`

### Requirement: Backfill SHALL report per-source outcomes
The backfill command SHALL present a normalized outcome for each attempted market-data category so users can distinguish populated, skipped, empty, and failed categories.

#### Scenario: Mixed outcome report
- **WHEN** a backfill run has one populated category, one unsupported category, and one failed category
- **THEN** the command SHALL show each category outcome separately
- **AND** the command SHALL include the requested trade date in the final summary

#### Scenario: Partial success remains successful cache work
- **WHEN** at least one category is written successfully
- **AND** one or more other categories are unsupported, empty, or failed
- **THEN** the command SHALL report partial completion rather than claiming a complete market-data snapshot

### Requirement: Backfill SHALL be idempotent by trade date and business key
The backfill workflow SHALL reuse existing market cache upsert semantics so repeated runs do not create duplicate rows.

#### Scenario: Re-running backfill updates existing rows
- **WHEN** cache rows already exist for the requested trade date and business key
- **AND** backfill receives validated replacement data for the same key
- **THEN** the system SHALL update the existing row
- **AND** it SHALL NOT insert a duplicate row

#### Scenario: Unsupported categories preserve existing valid cache
- **WHEN** a category already has valid cache rows for the requested trade date
- **AND** the backfill run marks that category as `skipped_unsupported`
- **THEN** the existing cache rows SHALL remain unchanged

