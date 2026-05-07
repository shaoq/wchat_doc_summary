## ADDED Requirements

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
