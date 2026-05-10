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
## Requirements
### Requirement: Overseas market context cache SHALL preserve higher-quality context against degraded refreshes

The system SHALL avoid overwriting a cached overseas market context entry with a lower-quality refresh for the same target A-share trade date.

#### Scenario: Failed refresh does not replace usable cached context
- **WHEN** a trade date already has cached overseas market context with `status` `ok` or `partial`
- **AND** a later refresh for that same trade date produces `status` `error`
- **THEN** the cache SHALL preserve the existing usable overseas market context entry
- **AND** the failed refresh SHALL NOT replace it

### Requirement: Overseas market context cache SHALL retain provider provenance

The system SHALL persist enough provider provenance for cached overseas market context to explain how the stored result was produced.

#### Scenario: Cached context retains effective source metadata
- **WHEN** the system saves overseas market context for a target A-share trade date
- **THEN** the cached record SHALL retain the effective `source`
- **AND** it SHALL retain any stored provider attempt metadata required by downstream replay or diagnostics

### Requirement: Cache SHALL persist overseas market context by target A-share trade date

The market-summary cache layer SHALL be able to persist overseas market context records associated with a target A-share trade date without collapsing their independent capture-time semantics.

#### Scenario: Save overseas context with target-date linkage
- **WHEN** the system saves market-summary-related cache data for a target A-share trade date
- **AND** a normalized overseas market context payload is available
- **THEN** the cache layer SHALL persist that payload with a link to the target A-share trade date
- **AND** it SHALL preserve the overseas context capture metadata needed for later replay

### Requirement: Cache reads SHALL replay overseas market context in normalized form

The cache layer SHALL return overseas market context using the same normalized structure that live summary generation consumes.

#### Scenario: Cached overseas context matches live contract
- **WHEN** cached market-summary data is loaded for a trade date that has saved overseas context
- **THEN** the returned payload SHALL expose overseas market context using the same field structure expected by CLI rendering and AI prompt generation

### Requirement: Missing overseas context SHALL remain an explicit cache miss

The cache layer SHALL preserve the distinction between “no cached overseas context exists” and “an overseas context record exists but is degraded”.

#### Scenario: Historical cache miss stays visible
- **WHEN** a historical trade date has cached A-share market data but no cached overseas market context
- **THEN** the cache read result SHALL indicate that overseas context is unavailable for that trade date
- **AND** downstream summary generation SHALL be able to surface that absence instead of silently inventing fallback values

