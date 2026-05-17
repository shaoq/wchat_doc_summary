## ADDED Requirements

### Requirement: System SHALL define sector group trend stage semantics
The system SHALL define each supported sector-group `trend_status` value with stable semantics focused on cross-member structure.

#### Scenario: Group report uses supported stage definitions
- **WHEN** the system generates a sector group trend report
- **THEN** the prompt or equivalent generation contract SHALL include definitions for `暂无趋势`, `短线脉冲`, `低位启动`, `主线共振`, `主线扩散`, `轮动分化`, `补涨蔓延`, and `高位退潮`
- **AND** the generated or persisted group `trend_status` SHALL use one of those defined meanings

#### Scenario: Group stage definitions distinguish single-member activity from group trend
- **WHEN** only one member has fresh active evidence and other members are missing, stale, or inactive
- **THEN** the group stage SHALL NOT be `主线共振`, `主线扩散`, or `补涨蔓延`
- **AND** it SHALL be constrained to `短线脉冲`, `低位启动`, or `暂无趋势` according to the evidence strength

#### Scenario: Group stage definitions distinguish resonance from diffusion
- **WHEN** multiple fresh members are active at the same time
- **THEN** the group stage SHALL be eligible for `主线共振`
- **AND** when activity is spreading from core members to peripheral members over time, the group stage SHALL be eligible for `主线扩散`

### Requirement: System SHALL apply group member freshness downgrade rules
The system SHALL restrict overconfident group stages when confirmed members lack fresh sector summaries or when candidate/stale members dominate the group evidence.

#### Scenario: Missing member summaries restrict group stages
- **WHEN** a sector group has no fresh member summaries for the target date
- **THEN** the group stage SHALL be constrained to `暂无趋势` or `短线脉冲`
- **AND** the report SHALL explicitly mention the member freshness limitation

#### Scenario: Stale member summaries prevent group resonance
- **WHEN** most member summaries are stale relative to the group report date
- **THEN** the group stage SHALL NOT be `主线共振` or `主线扩散`
- **AND** the group report SHALL mark the affected members as stale or missing

#### Scenario: Candidate members do not create confirmed group trend
- **WHEN** group activity relies mainly on members that remain `candidate`
- **THEN** the group stage SHALL NOT be `主线共振`, `主线扩散`, or `补涨蔓延`
- **AND** the report SHALL treat that evidence as provisional

### Requirement: System SHALL constrain group stages using member sector states
The system SHALL validate group `trend_status` against member sector trend states, relation metadata, and available freshness data.

#### Scenario: Group resonance requires multiple active members
- **WHEN** a group is assigned `主线共振`
- **THEN** multiple confirmed members SHALL have fresh active sector stages such as `低位启动`, `轮动补涨`, `主线延续`, `主线加强`, or `分歧中继`
- **AND** at least one active member SHALL be a core or high-weight member when relation metadata is available

#### Scenario: Group diffusion requires core-to-peripheral spread
- **WHEN** a group is assigned `主线扩散`
- **THEN** the evidence SHALL show core or high-weight members active before or alongside related, upstream, downstream, catalyst, or lower-weight members joining
- **AND** the report SHALL identify the core and spreading members where available

#### Scenario: Group rotation divergence requires mixed member states
- **WHEN** a group is assigned `轮动分化`
- **THEN** member states SHALL show mixed behavior, such as some members active while others are stale, weakening, `暂无趋势`, or `高位退潮`
- **AND** the report SHALL describe the divergence without treating the whole group as synchronized

#### Scenario: Group catch-up spread requires non-core participation
- **WHEN** a group is assigned `补涨蔓延`
- **THEN** the evidence SHALL show non-core, downstream, related, or previously weaker members becoming active after core members have already been active
- **AND** the report SHALL distinguish catch-up members from core members where available

#### Scenario: Group retreat requires core or broad weakening
- **WHEN** a group is assigned `高位退潮`
- **THEN** the evidence SHALL show weakening in core/high-weight members or broad member deterioration from a prior active state
- **AND** weak groups without prior active context SHALL use `暂无趋势` rather than `高位退潮`

### Requirement: System SHALL preserve group stage labels independently from recommendations
The system SHALL treat group `trend_status` as a descriptive structure-stage label and not as a trading recommendation.

#### Scenario: Group stage can be displayed without action bias
- **WHEN** downstream views use group trend history for trend tables or matrices
- **THEN** the group `trend_status` and `strength_level` SHALL be sufficient to describe the group trend structure
- **AND** those views SHALL NOT need `action_bias` to interpret the group stage
