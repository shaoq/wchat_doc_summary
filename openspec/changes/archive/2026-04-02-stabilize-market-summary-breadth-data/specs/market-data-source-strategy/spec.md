## MODIFIED Requirements

### Requirement: Volume and rise-fall statistics share one market snapshot strategy

The system SHALL compute trading volume and rise-fall statistics from a shared validated full-market snapshot whenever the primary realtime snapshot source can provide a complete market sample.

#### Scenario: Shared realtime snapshot succeeds with complete sample
- **WHEN** the primary full-market snapshot source returns a complete paginated market snapshot
- **THEN** the system SHALL compute both volume and rise-fall statistics from that same snapshot
- **AND** the two outputs SHALL correspond to the same fetch moment
- **AND** the system SHALL mark both data items as successful breadth data

#### Scenario: Shared realtime snapshot is incomplete
- **WHEN** the primary full-market snapshot source returns only a partial sample or a sample whose record count does not match the upstream declared total
- **THEN** the system SHALL treat that snapshot as incomplete
- **AND** the system SHALL NOT treat the derived volume and rise-fall statistics as successful full-market breadth data
- **AND** the system SHALL attempt the declared fallback source before returning a degraded result

#### Scenario: Shared realtime snapshot and fallback both fail
- **WHEN** the primary full-market snapshot source is unavailable, malformed, or incomplete and the declared fallback source also fails
- **THEN** the system SHALL return the normalized zero-value contracts for volume and rise-fall statistics
- **AND** the system SHALL mark both data items as degraded rather than successful

## ADDED Requirements

### Requirement: Breadth data exposes quality metadata to downstream consumers

The system SHALL expose explicit quality metadata for trading volume and rise-fall statistics so downstream consumers can distinguish complete realtime data from partial samples and failure fallbacks.

#### Scenario: Complete breadth data is returned
- **WHEN** volume and rise-fall statistics are computed from a validated complete market snapshot or a trusted fallback source
- **THEN** the market data payload SHALL include a quality status of `ok` for both data items
- **AND** the payload SHALL expose the source used for those data items

#### Scenario: Partial breadth sample is returned for diagnosis
- **WHEN** the system keeps a partial breadth sample for debugging or user-facing diagnosis
- **THEN** the market data payload SHALL include a quality status of `partial`
- **AND** the payload SHALL expose both the actual sample count and the expected total count when available

#### Scenario: Breadth data fully degrades
- **WHEN** the system falls back to normalized zero-value contracts because no usable breadth source succeeded
- **THEN** the market data payload SHALL include a quality status of `error`
- **AND** the zero-value payload SHALL remain structurally compatible with existing callers
