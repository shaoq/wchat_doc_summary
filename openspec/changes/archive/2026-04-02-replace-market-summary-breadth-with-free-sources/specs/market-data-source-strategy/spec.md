## MODIFIED Requirements

### Requirement: Volume and rise-fall statistics share one market snapshot strategy

The system SHALL compute trading volume and rise-fall statistics from a shared free-priority full-market breadth source whenever the primary breadth adapter is available.

#### Scenario: Shared free-priority breadth source succeeds
- **WHEN** the primary free breadth adapter returns usable full-market data
- **THEN** the system SHALL compute both volume and rise-fall statistics from the same breadth sample
- **AND** the two outputs SHALL correspond to the same fetch moment
- **AND** the resolved source strategy SHALL identify that the primary free breadth adapter was used

#### Scenario: Shared free-priority breadth source fails
- **WHEN** the primary free breadth adapter is unavailable or returns unusable data
- **THEN** the system SHALL attempt the declared fallback source for volume and rise-fall statistics
- **AND** if all sources fail, the system SHALL return the normalized zero-value contracts
- **AND** the resolved source strategy SHALL expose whether the result came from fallback or full failure
