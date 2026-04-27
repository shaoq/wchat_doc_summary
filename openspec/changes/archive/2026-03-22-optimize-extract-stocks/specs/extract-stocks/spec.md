## ADDED Requirements

### Requirement: Default output file path
The system SHALL automatically save extraction results to a default output path.

#### Scenario: Default output path format
- **WHEN** user runs extract-stocks without -o option
- **THEN** results SHALL be saved to `output/extract_stocks/{mp_id}_stocks_{YYMMDD}.txt`

#### Scenario: Custom output path overrides default
- **WHEN** user runs extract-stocks with -o option
- **THEN** results SHALL be saved to the specified path instead of default

#### Scenario: Output directory is created automatically
- **WHEN** the default output directory does not exist
- **THEN** the system SHALL create `output/extract_stocks/` directory
