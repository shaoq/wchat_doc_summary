## ADDED Requirements

### Requirement: Market data uses type-specific source strategies

The system SHALL define source selection independently for each market data type instead of relying on a single implicit global source order.

#### Scenario: Resolve sources by market data type
- **WHEN** the system requests market data for summary generation
- **THEN** index data, full-market snapshot data, sector ranking data, and limit-up stock data SHALL each use their own declared source strategy
- **AND** the strategy for one data type SHALL NOT implicitly determine the strategy for another data type

### Requirement: Index data keeps a stable dedicated fallback path

The system SHALL fetch major index data from a dedicated primary index source and SHALL fall back to a secondary index source if the primary source is unavailable.

#### Scenario: Primary index source succeeds
- **WHEN** the primary index source returns usable realtime index data
- **THEN** the system SHALL use that index data without calling the secondary source

#### Scenario: Primary index source fails
- **WHEN** the primary index source fails or returns unusable data
- **THEN** the system SHALL attempt the declared secondary index source
- **AND** the system SHALL still return the normalized index contract

### Requirement: Volume and rise-fall statistics share one market snapshot strategy

The system SHALL compute trading volume and rise-fall statistics from a shared full-market snapshot whenever the primary realtime snapshot source is available.

#### Scenario: Shared realtime snapshot succeeds
- **WHEN** the primary full-market snapshot source returns usable data
- **THEN** the system SHALL compute both volume and rise-fall statistics from the same snapshot
- **AND** the two outputs SHALL correspond to the same fetch moment

#### Scenario: Shared realtime snapshot fails
- **WHEN** the primary full-market snapshot source is unavailable or malformed
- **THEN** the system SHALL attempt the declared fallback source for volume and rise-fall statistics
- **AND** if all sources fail, the system SHALL return the normalized zero-value contracts

### Requirement: Sector data prefers a dedicated stable adapter

The system SHALL prefer a dedicated sector-data adapter as the primary source strategy for sector rankings, rather than depending primarily on the known fragile realtime curl path.

#### Scenario: Dedicated sector adapter succeeds
- **WHEN** the dedicated sector-data adapter returns usable sector rankings
- **THEN** the system SHALL use that adapter as the sector primary source
- **AND** the normalized output SHALL include stable top and bottom sector lists

#### Scenario: Dedicated sector adapter fails
- **WHEN** the dedicated sector-data adapter fails
- **THEN** the system SHALL attempt the declared backup adapter for sector rankings
- **AND** if all sector adapters fail, the system SHALL return an empty normalized sector payload

### Requirement: Limit-up data prefers a dedicated limit-up pool adapter

The system SHALL prefer a dedicated limit-up pool adapter as the primary source strategy for limit-up stocks, rather than relying primarily on ad-hoc filtering of the full-market realtime snapshot.

#### Scenario: Dedicated limit-up adapter succeeds
- **WHEN** the dedicated limit-up pool adapter returns usable limit-up data
- **THEN** the system SHALL use that adapter as the primary limit-up source
- **AND** the output SHALL still match the normalized limit-up contract

#### Scenario: Dedicated limit-up adapter fails
- **WHEN** the dedicated limit-up pool adapter fails
- **THEN** the system SHALL attempt the declared backup strategy for limit-up data
- **AND** if all limit-up strategies fail, the system SHALL return an empty normalized limit-up list
