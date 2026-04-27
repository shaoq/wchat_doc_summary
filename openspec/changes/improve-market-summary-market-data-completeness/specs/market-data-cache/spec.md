## MODIFIED Requirements

### Requirement: Cache writes SHALL protect validated breadth data

The system SHALL only write trading volume and rise-fall statistics cache rows when those breadth data items are marked as cache-eligible quality results, and SHALL continue to protect previously validated cache rows from being overwritten by degraded results.

#### Scenario: Save validated breadth data
- **WHEN** market data is saved and the breadth quality status for volume and rise-fall statistics is `ok`
- **THEN** the system SHALL insert or update the corresponding `market_volume` and `market_statistics` rows for that trade date

#### Scenario: Save near-complete rise-fall statistics
- **WHEN** market data is saved and the rise-fall statistics quality status is `near-complete`
- **THEN** the system SHALL treat that statistics result as cache-eligible
- **AND** it SHALL insert or update the corresponding `market_statistics` row for that trade date

#### Scenario: Skip invalid breadth cache writes
- **WHEN** market data is saved and the breadth quality status for volume or rise-fall statistics is `partial` or `error`
- **THEN** the system SHALL skip writes for the invalid breadth table rows
- **AND** the save operation SHALL continue for other valid market data tables

#### Scenario: Invalid breadth fetch does not overwrite valid cache
- **WHEN** a trade date already has cached validated breadth data
- **AND** a later fetch for that same trade date produces `partial` or `error` breadth status for one of those items
- **THEN** the system SHALL preserve the existing validated cache row for that item
- **AND** the degraded fetch SHALL NOT replace it with degraded or zero-value data
