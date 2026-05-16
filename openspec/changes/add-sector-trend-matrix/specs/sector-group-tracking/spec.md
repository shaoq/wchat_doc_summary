## ADDED Requirements

### Requirement: System SHALL provide sector group trend matrix views
The system SHALL provide matrix-style views that display sector group trend stages and strength levels across report dates.

#### Scenario: Latest group trend matrix
- **WHEN** a user requests the latest group trend matrix
- **THEN** the system SHALL list groups with their latest report date, `trend_status`, `strength_level`, descriptive change state, member count when available, and report path when available
- **AND** the default view SHALL NOT require reading individual Markdown report files

#### Scenario: Historical group trend matrix
- **WHEN** a user requests a group trend matrix for recent dates
- **THEN** the system SHALL render groups as rows and report dates as columns
- **AND** each populated date cell SHALL include the group `trend_status` and `strength_level`
- **AND** missing date cells SHALL be rendered as missing rather than inferred

#### Scenario: Group matrix hides recommendation bias by default
- **WHEN** the system renders a group trend matrix
- **THEN** it SHALL omit `action_bias` by default
- **AND** it SHALL treat the matrix as descriptive group-structure output rather than recommendation output

### Requirement: System SHALL provide group-expanded member trend matrices
The system SHALL allow a selected sector group to be expanded into a matrix containing the group row and its member sector rows.

#### Scenario: Group-expanded matrix includes group and members
- **WHEN** a user requests a matrix for group `光伏产业链`
- **THEN** the system SHALL include a group-level row for `光伏产业链`
- **AND** it SHALL include confirmed member sector rows for that group
- **AND** member rows SHALL display relation type or equivalent membership metadata when available

#### Scenario: Group-expanded matrix preserves sector identity
- **WHEN** a sector belongs to multiple groups
- **THEN** the group-expanded matrix SHALL display the sector under the selected group membership
- **AND** it SHALL NOT merge, rename, or duplicate the underlying sector identity outside that view

#### Scenario: Group-expanded matrix handles missing group summaries
- **WHEN** a selected group has missing group-level summaries for some dates but member sector summaries exist
- **THEN** the matrix SHALL render missing group cells as missing
- **AND** it SHALL still render available member sector cells for those dates

### Requirement: System SHALL compute group trend change states
The system SHALL compute a descriptive latest-change state for group matrix rows using prior available group summaries.

#### Scenario: Group change state identifies new rows
- **WHEN** a group has a current summary but no prior summary in the matrix comparison window
- **THEN** the group change state SHALL be `新增`

#### Scenario: Group change state identifies warming
- **WHEN** the current group stage ranks higher than the prior available group stage
- **THEN** the group change state SHALL be `升温`

#### Scenario: Group change state identifies cooling or weakening
- **WHEN** the current group stage ranks lower than the prior available group stage but remains active
- **THEN** the group change state SHALL be `降温`
- **AND** when the current group stage becomes `暂无趋势` or `高位退潮`, the change state SHALL be `转弱`

#### Scenario: Group change state handles missing current summaries
- **WHEN** a group has prior summaries but no current summary for the selected latest date
- **THEN** the group change state SHALL be `缺失`

### Requirement: System SHALL export group trend matrices to Markdown
The system SHALL allow group trend matrices and group-expanded member matrices to be written as Markdown files for review and archival.

#### Scenario: Group matrix markdown export
- **WHEN** a user requests Markdown export for a group trend matrix
- **THEN** the system SHALL write a Markdown table containing the selected group rows and date columns
- **AND** the export SHALL include report paths or links where available

#### Scenario: Group-expanded markdown export
- **WHEN** a user requests Markdown export for a selected group-expanded matrix
- **THEN** the system SHALL write a Markdown table containing the selected group row and member sector rows
- **AND** the export SHALL identify member relation types when available

#### Scenario: Default group matrix export path
- **WHEN** a user requests Markdown export without an explicit output path
- **THEN** the system SHALL write the matrix under `output/trend_matrices/`
- **AND** it SHALL use a path that does not overwrite individual group or sector reports
