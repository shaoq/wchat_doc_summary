## ADDED Requirements

### Requirement: System SHALL provide sector trend matrix views
The system SHALL provide matrix-style views that display sector trend stages and strength levels across report dates.

#### Scenario: Latest sector trend matrix
- **WHEN** a user requests the latest sector trend matrix
- **THEN** the system SHALL list sectors with their latest report date, `trend_status`, `strength_level`, descriptive change state, and report path when available
- **AND** the default view SHALL NOT require reading individual Markdown report files

#### Scenario: Historical sector trend matrix
- **WHEN** a user requests a sector trend matrix for recent dates
- **THEN** the system SHALL render sectors as rows and report dates as columns
- **AND** each populated date cell SHALL include the sector `trend_status` and `strength_level`
- **AND** missing date cells SHALL be rendered as missing rather than inferred

#### Scenario: Sector matrix hides recommendation bias by default
- **WHEN** the system renders a sector trend matrix
- **THEN** it SHALL omit `action_bias` by default
- **AND** it SHALL treat the matrix as descriptive trend-state output rather than recommendation output

### Requirement: System SHALL compute sector trend change states
The system SHALL compute a descriptive latest-change state for sector matrix rows using prior available sector summaries.

#### Scenario: Sector change state identifies new rows
- **WHEN** a sector has a current summary but no prior summary in the matrix comparison window
- **THEN** the sector change state SHALL be `新增`

#### Scenario: Sector change state identifies warming
- **WHEN** the current sector stage ranks higher than the prior available sector stage
- **THEN** the sector change state SHALL be `升温`

#### Scenario: Sector change state identifies cooling or weakening
- **WHEN** the current sector stage ranks lower than the prior available sector stage but remains active
- **THEN** the sector change state SHALL be `降温`
- **AND** when the current sector stage becomes `暂无趋势` or `高位退潮`, the change state SHALL be `转弱`

#### Scenario: Sector change state handles missing current summaries
- **WHEN** a sector has prior summaries but no current summary for the selected latest date
- **THEN** the sector change state SHALL be `缺失`

### Requirement: System SHALL export sector trend matrices to Markdown
The system SHALL allow sector trend matrices to be written as Markdown files for review and archival.

#### Scenario: Sector matrix markdown export
- **WHEN** a user requests Markdown export for a sector trend matrix
- **THEN** the system SHALL write a Markdown table containing the selected sector rows and date columns
- **AND** the export SHALL include report paths or links where available

#### Scenario: Default sector matrix export path
- **WHEN** a user requests Markdown export without an explicit output path
- **THEN** the system SHALL write the matrix under `output/trend_matrices/`
- **AND** it SHALL use a date-based or `latest.md` path that does not overwrite individual sector reports
