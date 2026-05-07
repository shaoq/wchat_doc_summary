## ADDED Requirements

### Requirement: Overseas market context SHALL support ordered provider fallback

The system SHALL attempt overseas market context collection through a declared ordered provider chain instead of relying on a single upstream endpoint.

#### Scenario: Fallback provider succeeds after primary provider failure
- **WHEN** the primary overseas market context provider returns an unusable result
- **THEN** the system SHALL attempt the next configured provider in order
- **AND** the final `global_market_context` payload SHALL remain consumable if a later provider succeeds

### Requirement: Overseas market context SHALL expose normalized provider failure categories

The system SHALL normalize upstream provider failures into structured failure categories that downstream consumers can interpret without parsing raw exception text.

#### Scenario: Unauthorized upstream is classified explicitly
- **WHEN** an overseas market context provider returns HTTP 401 or an equivalent authorization failure
- **THEN** the provider attempt result SHALL expose `failure_type` as `unauthorized`
- **AND** the failure SHALL remain distinguishable from empty, malformed, rate-limited, or network failures

### Requirement: Overseas market context SHALL record final source and attempt metadata

The system SHALL include structured provider provenance in the normalized overseas market context payload.

#### Scenario: Payload records fallback provenance
- **WHEN** the final overseas market context payload is built
- **THEN** it SHALL include the effective `source`
- **AND** it SHALL include a `source_attempts` array in provider attempt order
- **AND** it SHALL indicate whether the final payload was produced through degraded fallback instead of the primary provider
