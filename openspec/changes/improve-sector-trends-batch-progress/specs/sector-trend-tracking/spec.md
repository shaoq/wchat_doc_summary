## MODIFIED Requirements

### Requirement: System SHALL batch update tracked sectors
The system SHALL support batch updating sectors by applying the same single-sector update workflow to multiple tracked sectors and reporting real-time progress for long-running batch work.

#### Scenario: All update processes tracked sectors only
- **WHEN** a user runs `wchat ai sector-trends update --all`
- **THEN** the system SHALL select sectors with status `tracked`
- **AND** it SHALL not update candidate sectors unless the user supplies an explicit include-candidates option

#### Scenario: All update executes per sector
- **WHEN** the system runs a batch sector update
- **THEN** it SHALL execute the single-sector evidence collection and AI generation workflow independently for each selected sector
- **AND** one sector result SHALL NOT be merged into another sector's report

#### Scenario: Batch update reports progress and summary
- **WHEN** a user runs `wchat ai sector-trends update --all`
- **THEN** the CLI SHALL report batch context before long-running work begins
- **AND** it SHALL show the current sector index, total sector count, sector name, active stage, and per-sector result as the batch runs
- **AND** when the batch completes, it SHALL report successful, skipped, and failed sector counts
- **AND** it SHALL show per-sector status for the run

#### Scenario: Batch update reports shared repair progress
- **WHEN** a batch sector update runs shared CLS watch repair
- **THEN** the CLI SHALL report when shared repair starts
- **AND** it SHALL report whether shared repair completed or failed before per-sector updates continue
- **AND** a shared repair failure SHALL NOT hide that the batch continued with existing data

#### Scenario: Batch update reports AI retries
- **WHEN** AI generation retries during a batch sector update
- **THEN** the CLI SHALL report the retry attempt and maximum attempts for the current sector
- **AND** it SHALL include a sanitized error summary
- **AND** it SHALL NOT print secrets, API keys, or full provider URLs

#### Scenario: Batch update honors skip preparation
- **WHEN** a user runs `wchat ai sector-trends update --all --skip-preparation`
- **THEN** per-sector evidence preparation SHALL be skipped for every sector in the batch
- **AND** the batch progress output SHALL NOT report preparation as an executed stage for those sectors
