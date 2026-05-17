## ADDED Requirements

### Requirement: System SHALL define sector trend stage semantics
The system SHALL define each supported single-sector `trend_status` value with stable semantics and evidence expectations so sector trend labels are comparable across reports.

#### Scenario: Sector report uses supported stage definitions
- **WHEN** the system generates a sector trend report
- **THEN** the prompt or equivalent generation contract SHALL include definitions for `暂无趋势`, `短线脉冲`, `低位启动`, `轮动补涨`, `主线延续`, `主线加强`, `分歧中继`, and `高位退潮`
- **AND** the generated or persisted `trend_status` SHALL use one of those defined meanings

#### Scenario: Sector stage definitions distinguish pulse from startup
- **WHEN** sector evidence shows only a single-day or isolated short-window move without continuity or breadth
- **THEN** the sector stage SHALL NOT be `低位启动`, `主线延续`, or `主线加强`
- **AND** it SHALL be constrained to `短线脉冲` or `暂无趋势`

#### Scenario: Sector stage definitions distinguish startup from mainline continuation
- **WHEN** sector evidence is fresh and shows emerging multi-signal activity but lacks prior confirmed trend context
- **THEN** the sector stage SHALL be eligible for `低位启动`
- **AND** it SHALL NOT be `主线延续` unless the evidence window itself demonstrates sustained trend continuity

### Requirement: System SHALL apply sector evidence downgrade rules
The system SHALL restrict overconfident sector stages when evidence is sparse, stale, or missing critical source groups.

#### Scenario: Sparse sector evidence restricts allowed stages
- **WHEN** available sector evidence is marked sparse or has insufficient market and information-source support
- **THEN** the sector stage SHALL be constrained to `暂无趋势` or `短线脉冲`
- **AND** the report SHALL explicitly mention the evidence limitation

#### Scenario: Missing market evidence prevents mainline sector stages
- **WHEN** a sector has no matching market appearance records in the evidence window
- **THEN** the sector stage SHALL NOT be `主线加强`, `主线延续`, or `低位启动`
- **AND** the system SHALL prefer `暂无趋势` unless other fresh evidence supports `短线脉冲`

#### Scenario: Fresh multi-signal evidence can support low-level startup
- **WHEN** sector evidence includes fresh market activity plus at least one corroborating information source or repeated market appearances
- **THEN** the sector stage SHALL be eligible for `低位启动`
- **AND** it SHALL still remain below `主线延续` unless continuity is demonstrated

### Requirement: System SHALL constrain sector stage transitions
The system SHALL use prior sector summary context or sufficient in-window continuity before assigning stages that imply continuation, strengthening, or retreat.

#### Scenario: Mainline strengthening requires prior active context
- **WHEN** a sector is assigned `主线加强`
- **THEN** the system SHALL have either a prior active stage such as `低位启动`, `主线延续`, `分歧中继`, or `轮动补涨`
- **OR** the current evidence window SHALL demonstrate strong sustained multi-day activity without relying on a single isolated move

#### Scenario: High-level retreat requires a prior active state
- **WHEN** a sector is assigned `高位退潮`
- **THEN** the system SHALL have prior active trend context or current-window evidence showing retreat from a previously active state
- **AND** a sector with no prior active context and weak evidence SHALL use `暂无趋势` rather than `高位退潮`

#### Scenario: First sector report uses conservative initial stages
- **WHEN** a sector has no previous trend summary
- **THEN** the initial stage SHALL be constrained to `暂无趋势`, `短线脉冲`, or `低位启动` unless the evidence window demonstrates sustained trend continuity

### Requirement: System SHALL preserve sector stage labels independently from recommendations
The system SHALL treat sector `trend_status` as a descriptive trend-stage label and not as a trading recommendation.

#### Scenario: Sector stage can be displayed without action bias
- **WHEN** downstream views use sector trend history for trend tables or matrices
- **THEN** the sector `trend_status` and `strength_level` SHALL be sufficient to describe the trend state
- **AND** those views SHALL NOT need `action_bias` to interpret the sector stage
