## ADDED Requirements

### Requirement: CLS telegraphs can be ingested into local storage

The system SHALL provide a stable ingestion path that fetches财联社重要电报 and persists them into local storage for later summary generation.

#### Scenario: Persist telegraphs from remote source
- **WHEN** the system fetches telegraph items from the configured CLS telegraph source
- **THEN** it stores new telegraph items in the local `cls_telegraphs` table
- **AND** duplicate remote items SHALL NOT create duplicate local records

### Requirement: CLS watch items can be ingested into local storage

The system SHALL provide a stable ingestion path that fetches财联社看盘数据 and persists them into local storage for later summary generation.

#### Scenario: Persist watch items from remote source
- **WHEN** the system fetches watch items from the configured CLS watch source
- **THEN** it stores new watch items in the local `cls_watch_data` table
- **AND** duplicate remote items SHALL NOT create duplicate local records

### Requirement: Market summary news aggregation reads persisted news data

The system SHALL aggregate CLS telegraphs and CLS watch items for market summary from persisted local data instead of depending on raw remote responses during prompt assembly.

#### Scenario: Summary reads ingested telegraphs
- **WHEN** local telegraph data exists for the selected trade date
- **THEN** market summary aggregation reads those items from local storage
- **AND** the aggregated prompt input keeps telegraphs as a distinct source section

#### Scenario: Summary reads ingested watch items
- **WHEN** local watch data exists for the selected trade date
- **THEN** market summary aggregation reads those items from local storage
- **AND** the aggregated prompt input keeps watch items as a distinct source section
