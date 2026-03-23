## ADDED Requirements

### Requirement: Simple info output format
The extract_stocks command SHALL support an optional simple info output format.

#### Scenario: Simple info output when flag is set
- **WHEN** user runs `extract_stocks` with `--simple-info` flag
- **THEN** the system SHALL output an additional file with format `{mp_id}_stocks_{yymmdd}_info.txt`
- **AND** the file SHALL contain stocks grouped by 10, separated by commas
- **AND** each stock SHALL be in format `股票名(代码)`

#### Scenario: Default output unchanged
- **WHEN** user runs `extract_stocks` without `--simple-info` flag
- **THEN** the system SHALL only output the detailed format file
