## ADDED Requirements

### Requirement: Users can ingest CLS telegraphs from the CLI

The system SHALL provide a CLI command that allows users to fetch and persist CLS telegraphs independently of market summary generation.

#### Scenario: Fetch telegraphs on demand
- **WHEN** the user executes the telegraph ingestion CLI command
- **THEN** the system fetches telegraphs from the configured CLS source
- **AND** the system persists new telegraphs to local storage

### Requirement: Users can ingest CLS watch data from the CLI

The system SHALL provide a CLI command that allows users to fetch and persist CLS watch data independently of market summary generation.

#### Scenario: Fetch watch data on demand
- **WHEN** the user executes the watch-data ingestion CLI command
- **THEN** the system fetches watch data from the configured CLS source
- **AND** the system persists new watch items to local storage

### Requirement: Users can inspect local CLS data from the CLI

The system SHALL provide CLI commands to inspect locally stored CLS telegraphs and watch data for verification and troubleshooting.

#### Scenario: List local telegraphs
- **WHEN** the user executes the local telegraph listing command
- **THEN** the system displays recently stored CLS telegraphs

#### Scenario: List local watch data
- **WHEN** the user executes the local watch-data listing command
- **THEN** the system displays recently stored CLS watch items
