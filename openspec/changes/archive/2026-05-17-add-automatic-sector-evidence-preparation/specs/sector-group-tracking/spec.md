## ADDED Requirements

### Requirement: Group membership workflows SHALL run automatic member evidence preparation
The system SHALL automatically prepare evidence for group members when memberships are created or changed so group updates can consume structured member evidence without manual repair steps.

#### Scenario: Adding a group member prepares member evidence
- **WHEN** a user runs `wchat ai sector-trends groups add --group 人形机器人链 --sector 机器人`
- **THEN** the system SHALL create or update the group membership
- **AND** it SHALL run evidence preparation for the member and group relationship
- **AND** it SHALL NOT generate a group trend report as part of the membership edit

#### Scenario: Accepting a group suggestion prepares accepted members
- **WHEN** a user accepts a group suggestion that adds one or more members
- **THEN** the system SHALL run evidence preparation for accepted members
- **AND** it SHALL persist preparation diagnostics for the group or accepted relationships where supported

### Requirement: Group updates SHALL prepare group and member evidence before validation
The system SHALL run automatic evidence preparation for a group and its confirmed members before generating a group trend report.

#### Scenario: Group update prepares evidence before member refresh
- **WHEN** a user runs `wchat ai sector-trends groups update --group 人形机器人链 --date 2026-05-14`
- **THEN** the system SHALL prepare group-level and member-level evidence for the target date before generating the group report
- **AND** member refresh SHALL consume prepared evidence when sector reports need to be generated

#### Scenario: Batch group update prepares shared evidence
- **WHEN** a user runs `wchat ai sector-trends groups update --all --date 2026-05-14`
- **THEN** the system SHALL prepare shared watch, theme, and market proxy evidence for the target window where possible
- **AND** it SHALL apply group-specific preparation for each group before group validation

### Requirement: Group validation SHALL consider member evidence quality
The system SHALL use member evidence quality and freshness in group trend validation instead of relying only on final member `trend_status` labels.

#### Scenario: Proxy-backed active members can support group activity
- **WHEN** multiple confirmed group members are fresh
- **AND** those members have high-confidence proxy-backed market evidence plus fresh watch or telegraph confirmation
- **THEN** group validation MAY treat those members as active evidence for group-level stages
- **AND** it SHALL preserve diagnostics showing that activity was proxy-backed

#### Scenario: Final member no-trend label does not erase strong member evidence
- **WHEN** a member's final sector `trend_status` is `暂无趋势`
- **AND** the member has high-confidence prepared evidence with multi-source confirmation
- **THEN** group validation SHALL consider the member evidence quality before downgrading the group solely because of the final label

#### Scenario: Weak member evidence does not create group resonance
- **WHEN** group members only have low-confidence or stale prepared evidence
- **THEN** group validation SHALL continue to downgrade multi-member active stages such as `主线共振`, `主线扩散`, or `补涨蔓延`

#### Scenario: Existing active member labels remain sufficient evidence
- **WHEN** a group has multiple fresh confirmed members whose final sector labels are active stages
- **THEN** group validation SHALL treat those member labels as active member evidence
- **AND** it SHALL NOT downgrade solely because proxy evidence was not needed

### Requirement: Group reports SHALL expose preparation and proxy diagnostics
The system SHALL persist and display concise group preparation diagnostics so users can understand how group evidence was prepared and validated.

#### Scenario: Group evidence JSON includes preparation diagnostics
- **WHEN** a group trend report is generated after automatic evidence preparation
- **THEN** the persisted group evidence JSON SHALL include member preparation summaries, proxy-backed member counts, low-confidence ignored counts, and unresolved data gaps where available

#### Scenario: CLI output summarizes group preparation
- **WHEN** a group update command completes
- **THEN** the CLI output SHALL summarize automatic preparation actions such as repaired watch rows, prepared members, proxy-backed members, and unresolved gaps

### Requirement: Group reports SHALL synchronize final validated labels
The system SHALL use the final post-validation group labels consistently across Markdown reports, database summaries, CLI output, and downstream matrix or history consumers.

#### Scenario: Validated group label replaces AI raw label in Markdown
- **WHEN** AI generates a group report with `trend_status: 主线共振`
- **AND** service validation downgrades the final group label to `暂无趋势`
- **THEN** the saved Markdown report's authoritative structured label SHALL be `暂无趋势`
- **AND** the database group summary `trend_status` SHALL also be `暂无趋势`

#### Scenario: Group diagnostics explain label changes
- **WHEN** the final group label differs from the AI-proposed group label
- **THEN** persisted group evidence diagnostics SHALL include the raw label, final label, and validation reason where available
- **AND** CLI output SHALL use the final label while indicating that validation adjusted the raw label when practical

### Requirement: Group workflows SHALL preserve member identity boundaries
The system SHALL NOT merge member sectors or rewrite group memberships solely because automatic evidence preparation found related proxy evidence.

#### Scenario: Proxy evidence does not create a new membership
- **WHEN** evidence preparation finds a proxy sector related to an existing group
- **THEN** the system SHALL NOT add it as a confirmed group member unless a group command or accepted suggestion does so

#### Scenario: Proxy evidence does not merge sectors
- **WHEN** a group member uses proxy market evidence from another sector
- **THEN** the system SHALL keep both sector identities separate
- **AND** diagnostics SHALL identify the proxy relationship explicitly
