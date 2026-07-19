## ADDED Requirements

### Requirement: Sector tracking SHALL cold-start on the Shenwan industry taxonomy

The system SHALL track sectors using Shenwan level-1 (SW1) industry names and codes as the canonical identity, replacing the prior east-money concept taxonomy via cold start (no historical migration), because the TickFlow free tier provides industries, not concepts.

#### Scenario: Cold start rebuilds tracked sectors

- **WHEN** the taxonomy switch is applied
- **THEN** the system SHALL archive prior east-money sector history (`output/sector_trends/`, `output/sector_groups/`, `tracked_sectors`, `sector_trend_summaries`)
- **AND** it SHALL rebuild tracked sectors from SW1 industries

#### Scenario: New sector uses SW1 identity

- **WHEN** a sector is discovered or initialized after cold start
- **THEN** its `canonical_name` SHALL be the SW1 industry name
- **AND** its `sector_code` SHALL be the SW1 code (e.g. `SW1_xxxxxx`), not the east-money code (`BKxxxx`)

### Requirement: Sector evidence SHALL match within the SW1 taxonomy

The `collect_sector_evidence` matching SHALL use SW1 names consistently across `MarketSector` and `TrackedSector`, so evidence is not lost to cross-taxonomy mismatch.

#### Scenario: Evidence matched under SW1 taxonomy

- **WHEN** evidence is collected for a tracked sector
- **THEN** the matcher SHALL compare SW1 `MarketSector.sector_name` against SW1 `TrackedSector.canonical_name`
- **AND** it SHALL NOT degrade a sector to "no trend" solely due to taxonomy mismatch
