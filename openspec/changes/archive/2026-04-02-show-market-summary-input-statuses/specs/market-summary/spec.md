## ADDED Requirements

### Requirement: System shall display an AI input data manifest before summary generation

The system SHALL display a unified input data manifest immediately before the AI summary-generation stage begins. The manifest SHALL enumerate each market-summary input type individually and SHALL show, for each type, its normalized status and quantity-oriented summary.

#### Scenario: Show per-type input data manifest before AI generation
- **WHEN** `wchat ai market-summary` completes market data collection and news data collection and is about to start AI summary generation
- **THEN** the CLI SHALL display a pre-generation input data manifest between stage 2 and stage 3
- **AND** the manifest SHALL enumerate each input type individually instead of only grouping results by success, failure, or empty state
- **AND** each item in the manifest SHALL include the input type name, normalized status, and quantity or count summary

#### Scenario: Preserve normalized statuses in the manifest
- **WHEN** one or more input types complete with no data or fail during collection
- **THEN** the manifest SHALL preserve the normalized per-type status as success, empty, or error
- **AND** the manifest SHALL show the corresponding quantity-oriented summary for each listed input type

#### Scenario: Use stable input ordering in the manifest
- **WHEN** the pre-generation manifest is rendered
- **THEN** the CLI SHALL display market data input types before news-related input types
- **AND** the ordering within the manifest SHALL remain stable across runs so users can compare results by position
