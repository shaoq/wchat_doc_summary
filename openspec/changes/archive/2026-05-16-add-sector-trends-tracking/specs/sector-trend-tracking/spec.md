## ADDED Requirements

### Requirement: System SHALL expose a sector trend command group
The system SHALL provide a `wchat ai sector-trends` command group for sector-oriented trend tracking without changing the behavior of `wchat ai market-summary`.

#### Scenario: Sector trend command group appears in AI help
- **WHEN** a user runs `wchat ai --help`
- **THEN** the output SHALL include the `sector-trends` command group

#### Scenario: Market summary remains a separate command
- **WHEN** a user runs `wchat ai market-summary`
- **THEN** the system SHALL continue to execute the existing market-summary flow rather than sector-trends behavior

### Requirement: System SHALL discover candidate sectors
The system SHALL discover candidate sectors from available market and information sources, including cached market sector rows, current sector strength data, CLS watch sector tags, and local article or news signals when available.

#### Scenario: Discover creates candidate sectors
- **WHEN** a user runs `wchat ai sector-trends discover --days 10`
- **THEN** the system SHALL scan the configured recent evidence window
- **AND** it SHALL create or update sector records with status `candidate` for newly discovered sectors that are not already tracked, inactive, or ignored

#### Scenario: Discover preserves tracked status
- **WHEN** discover sees a sector that already has status `tracked`
- **THEN** the system SHALL update its discovery metadata without downgrading it to `candidate`

### Requirement: System SHALL list tracked and candidate sectors
The system SHALL allow users to view sectors that can be tracked or are already tracked, with status, discovery source, activity evidence, and latest update metadata.

#### Scenario: Default list shows tracked and candidate sectors
- **WHEN** a user runs `wchat ai sector-trends ls`
- **THEN** the output SHALL include both `tracked` and `candidate` sectors
- **AND** each row SHALL show the sector name, status, source summary, activity summary, and latest seen or updated date

#### Scenario: List filters candidate sectors
- **WHEN** a user runs `wchat ai sector-trends ls --status candidate`
- **THEN** the output SHALL include candidate sectors
- **AND** it SHALL exclude tracked, inactive, and ignored sectors

#### Scenario: List filters by activity window
- **WHEN** a user runs `wchat ai sector-trends ls --active-days 10`
- **THEN** the output SHALL prioritize or restrict sectors using evidence from the last 10 trading or calendar days according to the implemented sector evidence window semantics

### Requirement: System SHALL initialize sectors for tracking
The system SHALL allow a user to promote a candidate sector or manually supplied sector into the tracked set.

#### Scenario: Init promotes candidate sector
- **WHEN** a user runs `wchat ai sector-trends init --sector 半导体`
- **AND** `半导体` exists as a candidate sector
- **THEN** the system SHALL change the sector status to `tracked`
- **AND** it SHALL preserve discovery metadata and aliases already associated with the sector

#### Scenario: Init creates manual tracked sector
- **WHEN** a user runs `wchat ai sector-trends init --sector 新主题`
- **AND** no matching candidate or tracked sector exists
- **THEN** the system SHALL create a tracked sector record for `新主题`
- **AND** it SHALL mark the discovery source as manual or equivalent user-provided source metadata

### Requirement: System SHALL update a single sector trend
The system SHALL collect recent evidence for a specified sector and generate a sector-specific trend tracking report.

#### Scenario: Update tracked sector
- **WHEN** a user runs `wchat ai sector-trends update --sector 半导体 --days 10`
- **AND** `半导体` exists as a tracked sector
- **THEN** the system SHALL collect recent sector evidence for the 10-day window
- **AND** it SHALL generate a sector trend report for `半导体`
- **AND** it SHALL save the report under `output/sector_trends/半导体/<date>.md`

#### Scenario: Update auto-initializes missing sector
- **WHEN** a user runs `wchat ai sector-trends update --sector 半导体`
- **AND** no matching tracked sector exists
- **THEN** the system SHALL create or promote a tracked sector for `半导体`
- **AND** it SHALL generate the first sector trend report for that sector

#### Scenario: Update uses previous sector trend
- **WHEN** a tracked sector has a previous trend summary
- **AND** the user runs an update for that sector
- **THEN** the AI prompt SHALL include the previous trend status, judgement, confirmation signals, and invalidation conditions where available
- **AND** the generated report SHALL describe material changes compared with the previous update

#### Scenario: First update uses initial tracking form
- **WHEN** a tracked sector has no previous trend summary
- **AND** the user runs an update for that sector
- **THEN** the generated report SHALL identify the update as an initial tracking assessment
- **AND** it SHALL not require a prior-state comparison

### Requirement: System SHALL batch update tracked sectors
The system SHALL support batch updating sectors by applying the same single-sector update workflow to multiple tracked sectors.

#### Scenario: All update processes tracked sectors only
- **WHEN** a user runs `wchat ai sector-trends update --all`
- **THEN** the system SHALL select sectors with status `tracked`
- **AND** it SHALL not update candidate sectors unless the user supplies an explicit include-candidates option

#### Scenario: All update executes per sector
- **WHEN** the system runs a batch sector update
- **THEN** it SHALL execute the single-sector evidence collection and AI generation workflow independently for each selected sector
- **AND** one sector result SHALL NOT be merged into another sector's report

#### Scenario: Batch update reports progress and summary
- **WHEN** a batch sector update completes
- **THEN** the system SHALL report successful, skipped, and failed sector counts
- **AND** it SHALL show per-sector status for the run

### Requirement: System SHALL store reports by sector-first path
The system SHALL persist generated sector trend reports using a sector-first directory structure.

#### Scenario: Single-sector report path
- **WHEN** the system generates a report for sector `半导体` with end date `2026-05-15`
- **THEN** it SHALL write the report to `output/sector_trends/半导体/2026-05-15.md` or a path-safe equivalent mapped to the display name `半导体`

#### Scenario: Batch reports keep sector-first organization
- **WHEN** the system generates reports for multiple sectors on the same date
- **THEN** each sector SHALL receive its own `{sector}/{date}.md` report path
- **AND** any batch summary file SHALL be supplemental rather than the primary sector report

### Requirement: System SHALL provide sector trend viewing and history
The system SHALL allow users to view the latest trend summary and historical update records for a tracked sector.

#### Scenario: Show latest sector trend
- **WHEN** a user runs `wchat ai sector-trends show --sector 半导体`
- **THEN** the system SHALL display the latest saved trend summary for `半导体`
- **AND** it SHALL include the report path when available

#### Scenario: Show sector history
- **WHEN** a user runs `wchat ai sector-trends history --sector 半导体`
- **THEN** the system SHALL list saved trend updates for `半导体` in reverse chronological order
- **AND** each row SHALL include date, trend status, strength level, action bias, and report path when available

### Requirement: System SHALL use conservative sector deduplication
The system SHALL normalize and deduplicate sector records using high-confidence identity signals while avoiding automatic merges of related but distinct sectors.

#### Scenario: Same sector code merges records
- **WHEN** two discovered sector records share the same stable sector code
- **THEN** the system SHALL treat them as the same sector identity

#### Scenario: Same canonical name merges records
- **WHEN** two discovered sector records normalize to the same canonical sector name
- **THEN** the system SHALL treat them as the same sector identity

#### Scenario: Alias match merges records
- **WHEN** a discovered sector name matches an explicit alias of an existing sector
- **THEN** the system SHALL attach the evidence to the existing sector identity

#### Scenario: Related sectors are not automatically merged
- **WHEN** two sector names are semantically related but not confirmed equivalent, such as `半导体` and `先进封装`
- **THEN** the system SHALL NOT automatically merge them
- **AND** it MAY surface them as possible related candidates for user review

### Requirement: System SHALL generate structured sector trend reports
The system SHALL generate reports that focus on the specified sector as a long-term tracking object and include structured labels for downstream listing and history display.

#### Scenario: Report includes required tracking labels
- **WHEN** the system generates a sector trend report
- **THEN** the report or persisted metadata SHALL include `trend_status`, `strength_level`, and `action_bias`
- **AND** `trend_status` SHALL use the supported status set defined by the implementation

#### Scenario: Report includes required sections
- **WHEN** the system generates a sector trend report
- **THEN** the report SHALL include sections for tracking conclusion, changes since previous update, recent sector performance, catalysts and logic, stock linkage, trend judgement, and follow-up conditions

#### Scenario: Sparse evidence downgrades judgement
- **WHEN** available evidence is insufficient to support a directional sector judgement
- **THEN** the generated report SHALL explicitly state the evidence gap
- **AND** it SHALL use an observation or no-trend judgement rather than asserting a strong trend
