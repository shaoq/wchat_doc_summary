## MODIFIED Requirements

### Requirement: Rise-fall statistics use a pytdx A-share quote strategy

The system SHALL compute rise-fall statistics from `pytdx` quotes over an explicitly filtered A-share universe, and SHALL NOT attempt the legacy AKShare/东方财富 `spot_em` fallback path for rise-fall statistics.

#### Scenario: pytdx quote aggregation succeeds
- **WHEN** the system can fetch `pytdx` quotes for the maintained A-share universe
- **THEN** it SHALL compute `up_count`, `down_count`, and `flat_count` from `price` and `last_close`
- **AND** the universe SHALL only include supported A-share prefixes

#### Scenario: pytdx quote aggregation is partial
- **WHEN** the `pytdx` quote strategy returns an incomplete but non-zero sample
- **THEN** the system SHALL return the partial rise-fall statistics result together with a `partial` quality status
- **AND** it SHALL NOT attempt the legacy AKShare/东方财富 fallback path for that statistics request

#### Scenario: pytdx quote aggregation fails
- **WHEN** the `pytdx` quote strategy is unavailable, malformed, or returns no usable sample
- **THEN** the system SHALL return the normalized zero-value statistics contract with an `error` quality status
- **AND** it SHALL NOT attempt the legacy AKShare/东方财富 fallback path for that statistics request
