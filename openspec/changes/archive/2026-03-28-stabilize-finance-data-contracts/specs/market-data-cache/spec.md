## MODIFIED Requirements

### Requirement: Market summary uses a normalized cacheable market data payload
The system SHALL expose a unified market data payload for market summary generation, and cached payloads MUST use the same field structure as live finance-client payloads.

#### Scenario: Cached payload matches live structure
- **WHEN** the system returns cached market data for a trade date
- **THEN** the payload SHALL contain the same top-level keys and field names used by the finance client live market data retrieval
- **AND** index entries SHALL use `name`, `close`, and `change` fields
