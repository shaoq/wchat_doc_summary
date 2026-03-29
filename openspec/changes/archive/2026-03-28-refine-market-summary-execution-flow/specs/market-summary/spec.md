## ADDED Requirements

### Requirement: Local preflight validation runs before AI initialization

The system SHALL complete local preflight validation for `market-summary` before initializing AI-specific dependencies.

#### Scenario: Invalid date fails before AI initialization
- **WHEN** user runs `wchat ai market-summary --date invalid-date`
- **THEN** the command SHALL report a local date-format error
- **AND** the command SHALL NOT initialize `AIProcessor` or any LLM-dependent component

### Requirement: News aggregation exposes degradation semantics

The system SHALL preserve per-source news aggregation status and SHALL distinguish between complete success and degraded execution when one or more news sources fail.

#### Scenario: Single news source fails but command continues
- **WHEN** one of telegraphs, watch items, or articles fails during news aggregation
- **AND** the other news sources still complete with data or empty results
- **THEN** the system SHALL retain per-source statuses in the aggregated result
- **AND** the command SHALL continue to summary generation with an explicit degraded news-stage status instead of reporting full success

#### Scenario: Empty source is not treated as source failure
- **WHEN** a news source completes successfully but returns no items
- **THEN** the system SHALL mark that source as empty rather than error
- **AND** the command SHALL keep using the remaining available sources

## MODIFIED Requirements

### Requirement: Market summary can be saved and updated

The system SHALL support saving market summaries with upsert behavior and SHALL treat summary completion as a successful database update plus successful Markdown file persistence:
- If no summary exists for the trade date, insert a new record
- If a summary already exists for the trade date, update the existing record's content and data_sources
- The command completion state SHALL NOT be reported as successful until both database and file outputs are available

#### Scenario: Save new market summary
- **WHEN** saving a market summary for a date that has no existing record
- **THEN** a new record SHALL be inserted with the provided content
- **AND** the record's created_at SHALL be set to the current timestamp
- **AND** the Markdown output file for that trade date SHALL be written successfully

#### Scenario: Update existing market summary (upsert)
- **WHEN** saving a market summary for a date that already has a record
- **THEN** the existing record's content and data_sources SHALL be updated
- **AND** the record's created_at SHALL NOT be changed
- **AND** no UNIQUE constraint error SHALL occur
- **AND** the Markdown output file for that trade date SHALL reflect the updated content

#### Scenario: Save operation does not end in partial success
- **WHEN** summary persistence fails after only one storage target succeeds
- **THEN** the command SHALL surface a persistence failure instead of reporting summary generation as fully completed

#### Scenario: Force regenerate with --force flag
- **WHEN** user runs `wchat ai market-summary --force` for a date with existing summary
- **THEN** the existing summary SHALL be overwritten with new content
- **AND** the command SHALL complete successfully only after both database and file outputs are updated
