## MODIFIED Requirements

### Requirement: Return cached data when available

The system SHALL return cached data when querying market data for a trade date that already has cached records, and SHALL treat historical trade dates as cache-first reads.

#### Scenario: Return cached data
- **WHEN** user requests market data for a trade date
- **AND** that trade date has cached data in database
- **THEN** system returns cached data without calling external APIs

#### Scenario: Historical date without cache
- **WHEN** user requests market data for a past trade date
- **AND** that trade date has NO cached data
- **THEN** system SHALL only call a source that can return market data for that requested trade date
- **AND** the system SHALL NOT reuse current-day market data as an implicit fallback for the historical date

## ADDED Requirements

### Requirement: Cached market data stays aligned with the requested trade date

The system SHALL ensure that any market data written to cache for a trade date actually corresponds to that same trade date.

#### Scenario: Save aligned historical payload
- **WHEN** the system fetches market data for a historical trade date from a supported historical source
- **THEN** the system stores that payload under the requested trade date
- **AND** future cache reads for that trade date return the same aligned payload

#### Scenario: Reject mismatched live payload for historical date
- **WHEN** the user requests market data for a historical trade date
- **AND** the available source only returns current-day live market data
- **THEN** the system SHALL report that historical market data is unavailable
- **AND** the system SHALL NOT cache the current-day payload under the historical trade date

### Requirement: Force refresh preserves trade-date consistency

The system SHALL support force refresh to bypass cache while still preserving trade-date consistency.

#### Scenario: Force refresh with aligned data
- **WHEN** user requests market data with `--force` for a trade date
- **AND** a supported source can return market data for that same trade date
- **THEN** system ignores any cached data
- **AND** calls external APIs to fetch fresh data for the requested trade date
- **AND** updates cache if caching conditions are met

#### Scenario: Force refresh for historical date without supported source
- **WHEN** user requests market data with `--force` for a historical trade date
- **AND** no supported source can return market data for that trade date
- **THEN** the system SHALL report that fresh market data for the target trade date is unavailable
- **AND** the system SHALL NOT overwrite existing cache with mismatched current-day data
