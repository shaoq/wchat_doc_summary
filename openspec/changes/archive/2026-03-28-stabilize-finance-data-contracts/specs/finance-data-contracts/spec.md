## ADDED Requirements

### Requirement: Finance client exposes a normalized market data contract
The system SHALL expose a normalized output contract for aggregated finance data regardless of the underlying source adapter used for each data type.

#### Scenario: Aggregated market data structure
- **WHEN** the finance client returns aggregated market data
- **THEN** the payload SHALL expose normalized sections for `indices`, `volume`, `statistics`, `sectors`, `limit_up`, and `cls_telegraph`

### Requirement: Index data uses stable normalized fields
The system SHALL expose index entries using stable normalized field names.

#### Scenario: Normalized index entry
- **WHEN** the finance client returns index data for a market index
- **THEN** each index entry SHALL use `name`, `close`, and `change` fields
- **AND** upstream source-specific field names SHALL NOT leak into the public finance client contract

### Requirement: Finance data fallback behavior is type-specific and predictable
The system SHALL apply fallback behavior independently for each finance data type.

#### Scenario: Index primary source fails
- **WHEN** the primary index source fails
- **THEN** the finance client SHALL attempt the configured fallback source before returning empty index data

#### Scenario: Sector source fails
- **WHEN** the sector source fails
- **THEN** the finance client SHALL return an empty normalized sector ranking payload instead of raising an uncaught exception

#### Scenario: CLS telegraph source fails
- **WHEN** the CLS telegraph source fails
- **THEN** the finance client SHALL return an empty normalized telegraph list instead of raising an uncaught exception

### Requirement: Empty-value semantics are stable across consumers
The system SHALL expose stable empty-value semantics so that cache and summary consumers can rely on them without per-source branching.

#### Scenario: No volume data available
- **WHEN** volume data is unavailable
- **THEN** the finance client SHALL return a normalized volume payload containing zero values

#### Scenario: No statistics data available
- **WHEN** market rise/fall statistics are unavailable
- **THEN** the finance client SHALL return a normalized statistics payload containing zero values
