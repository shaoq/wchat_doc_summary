## ADDED Requirements

### Requirement: Cache SHALL persist overseas market context by target A-share trade date

The market-summary cache layer SHALL be able to persist overseas market context records associated with a target A-share trade date without collapsing their independent capture-time semantics.

#### Scenario: Save overseas context with target-date linkage
- **WHEN** the system saves market-summary-related cache data for a target A-share trade date
- **AND** a normalized overseas market context payload is available
- **THEN** the cache layer SHALL persist that payload with a link to the target A-share trade date
- **AND** it SHALL preserve the overseas context capture metadata needed for later replay

### Requirement: Cache reads SHALL replay overseas market context in normalized form

The cache layer SHALL return overseas market context using the same normalized structure that live summary generation consumes.

#### Scenario: Cached overseas context matches live contract
- **WHEN** cached market-summary data is loaded for a trade date that has saved overseas context
- **THEN** the returned payload SHALL expose overseas market context using the same field structure expected by CLI rendering and AI prompt generation

### Requirement: Missing overseas context SHALL remain an explicit cache miss

The cache layer SHALL preserve the distinction between “no cached overseas context exists” and “an overseas context record exists but is degraded”.

#### Scenario: Historical cache miss stays visible
- **WHEN** a historical trade date has cached A-share market data but no cached overseas market context
- **THEN** the cache read result SHALL indicate that overseas context is unavailable for that trade date
- **AND** downstream summary generation SHALL be able to surface that absence instead of silently inventing fallback values
