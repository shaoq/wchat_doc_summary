## ADDED Requirements

### Requirement: Market summary uses a normalized cacheable market data payload
The system SHALL expose a unified market data payload for market summary generation, and cached payloads MUST use the same field structure as live payloads.

#### Scenario: Cached payload matches live structure
- **WHEN** the system returns cached market data for a trade date
- **THEN** the payload SHALL contain the same top-level keys and field names used by live market data retrieval
- **AND** index entries SHALL use `name`, `close`, and `change` fields

### Requirement: Historical trade dates use cache-first retrieval
The system SHALL prefer cached market data for completed historical trade dates and SHALL backfill the cache when data is missing.

#### Scenario: Historical trade date cache hit
- **WHEN** the user generates a market summary for a historical trade date and cached market data exists
- **THEN** the system SHALL use the cached payload
- **AND** the system SHALL NOT call external market data sources for that trade date

#### Scenario: Historical trade date cache miss
- **WHEN** the user generates a market summary for a historical trade date and no cached market data exists
- **THEN** the system SHALL fetch market data from external sources
- **AND** the system SHALL persist the fetched payload for later reuse

### Requirement: Force refresh bypasses cached market data
The system SHALL allow users to bypass existing cached market data when they explicitly request a force refresh.

#### Scenario: Force refresh on historical trade date
- **WHEN** the user executes market summary generation with `--force`
- **THEN** the system SHALL ignore any existing cached market data for the target trade date
- **AND** the system SHALL fetch a fresh market data payload
- **AND** the system SHALL update the stored cache when the trade date is eligible for caching

### Requirement: Offline mode replays local cached market data only
The system SHALL use only local cached market data in offline mode.

#### Scenario: Offline mode with cached data
- **WHEN** the user executes market summary generation with `--offline` and cached market data exists for the target trade date
- **THEN** the system SHALL use the cached market data payload
- **AND** the system SHALL NOT perform network requests for market data

#### Scenario: Offline mode without cached data
- **WHEN** the user executes market summary generation with `--offline` and cached market data does not exist for the target trade date
- **THEN** the system SHALL report that local market data is unavailable
- **AND** the system SHALL NOT silently substitute an empty live-equivalent payload
