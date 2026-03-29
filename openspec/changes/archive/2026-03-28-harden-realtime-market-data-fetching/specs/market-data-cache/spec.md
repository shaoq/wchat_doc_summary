## MODIFIED Requirements

### Requirement: Store sector data

The system SHALL store sector data in `market_sectors` table using a stable per-sector identifier for each trade date, even when the upstream realtime source does not expose a native sector code.

#### Scenario: Store multiple sectors
- **WHEN** sector data is cached
- **THEN** each sector is stored as a separate row
- **AND** the cache key for each row SHALL remain stable for that source representation on the same trade date

#### Scenario: Upstream source lacks native sector code
- **WHEN** realtime sector data is fetched from a source that does not expose a native sector code
- **THEN** the system SHALL derive a stable identifier before writing cache rows
- **AND** the cache write SHALL NOT rely on an empty shared identifier for multiple sectors
