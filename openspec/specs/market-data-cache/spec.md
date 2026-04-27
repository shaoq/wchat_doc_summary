## ADDED Requirements

### Requirement: Cache writes SHALL protect validated breadth data

The system SHALL only write trading volume and rise-fall statistics rows to cache when those breadth data items are marked as validated successful results.

#### Scenario: Save validated breadth data
- **WHEN** market data is saved and the breadth quality status for volume and rise-fall statistics is `ok`
- **THEN** the system SHALL insert or update the corresponding `market_volume` and `market_statistics` rows for that trade date

#### Scenario: Skip invalid breadth cache writes
- **WHEN** market data is saved and the breadth quality status for volume or rise-fall statistics is `partial` or `error`
- **THEN** the system SHALL skip writes for the invalid breadth table rows
- **AND** the save operation SHALL continue for other valid market data tables

#### Scenario: Invalid breadth fetch does not overwrite valid cache
- **WHEN** a trade date already has cached validated breadth data
- **AND** a later fetch for that same trade date produces `partial` or `error` breadth status
- **THEN** the system SHALL preserve the existing validated `market_volume` and `market_statistics` rows
- **AND** the invalid breadth fetch SHALL NOT replace them with degraded zero-value rows
