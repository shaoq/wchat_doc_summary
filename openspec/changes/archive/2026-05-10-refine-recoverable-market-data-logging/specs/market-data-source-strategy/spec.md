## ADDED Requirements

### Requirement: Recoverable market data source failures are not default warnings

The system SHALL distinguish recoverable source-attempt failures from final market data source failures in default logs.

#### Scenario: pytdx host fails but later host succeeds
- **WHEN** rise-fall statistics collection attempts multiple pytdx hosts
- **AND** one pytdx host fails
- **AND** a later pytdx host returns usable quote statistics
- **THEN** the failed host attempt SHALL NOT be emitted as a default warning
- **AND** the final statistics quality SHALL reflect the successful or near-complete result
- **AND** diagnostic details for the failed host SHALL remain available at debug level or equivalent internal diagnostics

#### Scenario: all pytdx hosts fail
- **WHEN** rise-fall statistics collection exhausts all configured pytdx hosts without usable quote statistics
- **THEN** the system SHALL emit one default warning summarizing the final pytdx statistics failure
- **AND** the warning SHALL indicate that all configured hosts were exhausted
- **AND** the returned statistics contract SHALL remain normalized as zero values with error or partial quality according to existing quality rules

### Requirement: Global market provider attempts are logged by final outcome

The system SHALL treat global-market provider failures as recoverable until the provider chain is exhausted.

#### Scenario: Yahoo quote fails but chart fallback succeeds
- **WHEN** global market context collection receives a failure from the Yahoo quote provider
- **AND** the Yahoo chart fallback provider returns usable global market context
- **THEN** the Yahoo quote failure SHALL NOT be emitted as a default warning
- **AND** the returned context SHALL include `degraded=true`
- **AND** the returned context SHALL include `source_attempts` that identify the Yahoo quote failure type and the successful fallback provider

#### Scenario: all global market providers fail
- **WHEN** global market context collection exhausts all configured providers without usable context
- **THEN** the system SHALL emit one default warning summarizing the final global market context failure
- **AND** the warning SHALL include provider-level failure categories when available
- **AND** the returned context SHALL have `status=error` and preserve the attempted provider sequence
