## MODIFIED Requirements

### Requirement: Force refresh cache

The system SHALL support force refresh to bypass cache reads and fetch fresh data from APIs. When cached rows for the same trade date already exist, the system SHALL update those rows by their business uniqueness keys instead of inserting duplicates.

#### Scenario: Force refresh with existing cache
- **WHEN** user requests market data with `--force` flag
- **AND** that trade date already has cached market data
- **THEN** system ignores cached data for reads
- **AND** calls external APIs to fetch fresh data
- **AND** updates cached rows for that trade date without UNIQUE constraint errors

#### Scenario: Force refresh without cache
- **WHEN** user requests market data with `--force` flag
- **AND** that trade date has no cached market data
- **THEN** system calls external APIs to fetch fresh data
- **AND** stores the fetched data if caching conditions are met

## ADDED Requirements

### Requirement: Cache writes are idempotent by table uniqueness keys

The system SHALL treat repeated saves for the same market data snapshot scope as upserts keyed by each table's declared uniqueness rule:
- `market_indices`, `market_volume`, and `market_statistics` by `trade_date`
- `market_sectors` by `trade_date + sector_code`
- `limit_up_stocks` by `trade_date + stock_code`

#### Scenario: Save the same trade date twice
- **WHEN** market data is saved twice for the same `trade_date`
- **THEN** single-row cache tables SHALL update the existing row for that `trade_date`
- **AND** composite-key cache tables SHALL update existing rows with matching composite keys
- **AND** the save operation SHALL complete without UNIQUE constraint errors

#### Scenario: Repeated save updates cached values
- **WHEN** market data is saved for a `trade_date` that already has cached rows
- **AND** the new payload contains different index, volume, statistics, sector, or limit-up values for existing keys
- **THEN** the cached rows for those keys SHALL reflect the new values after the save completes
- **AND** the number of rows per uniqueness key SHALL remain one
