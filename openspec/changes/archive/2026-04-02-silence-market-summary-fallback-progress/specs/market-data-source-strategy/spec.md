## MODIFIED Requirements

### Requirement: Volume and rise-fall statistics share one market snapshot strategy

The system SHALL compute trading volume and rise-fall statistics from a shared full-market snapshot whenever either the primary realtime snapshot source or the declared fallback full-market snapshot source is used.

#### Scenario: Shared realtime snapshot succeeds
- **WHEN** the primary full-market snapshot source returns usable data
- **THEN** the system SHALL compute both volume and rise-fall statistics from the same snapshot
- **AND** the two outputs SHALL correspond to the same fetch moment

#### Scenario: Shared fallback snapshot succeeds
- **WHEN** the primary full-market snapshot source is unavailable or malformed and the declared fallback full-market snapshot source returns usable data
- **THEN** the system SHALL derive both volume and rise-fall statistics from that same fallback snapshot
- **AND** the fallback path SHALL NOT trigger independent duplicated full-market fetches for volume and rise-fall statistics

#### Scenario: Shared realtime and fallback snapshots both fail
- **WHEN** the primary and fallback full-market snapshot sources are both unavailable or malformed
- **THEN** the system SHALL return the normalized zero-value contracts for both volume and rise-fall statistics
- **AND** the system SHALL resolve the fallback outcome once for the shared width-data path rather than exposing overlapping per-metric collection runs
