## ADDED Requirements

### Requirement: Sector workflows SHALL run automatic evidence preparation
The system SHALL automatically prepare local evidence for newly initialized and updated sectors so users do not need to manually run repair or mapping commands before trend analysis.

#### Scenario: Init prepares a newly tracked sector
- **WHEN** a user runs `wchat ai sector-trends init --sector 机器人`
- **THEN** the system SHALL create or promote the tracked sector
- **AND** it SHALL run evidence preparation for the sector using recent local data
- **AND** it SHALL update preparation diagnostics without generating a sector trend report

#### Scenario: Update prepares evidence before trend generation
- **WHEN** a user runs `wchat ai sector-trends update --sector 机器人 --date 2026-05-14 --days 10`
- **THEN** the system SHALL run evidence preparation for the target sector and evidence window before collecting trend evidence
- **AND** the generated report SHALL use prepared structured watch, alias, theme, and market proxy evidence where eligible

#### Scenario: Batch update prepares shared window evidence
- **WHEN** a user runs `wchat ai sector-trends update --all --date 2026-05-14 --days 10`
- **THEN** the system SHALL prepare shared window evidence once where possible
- **AND** it SHALL prepare per-sector aliases, theme links, and market evidence roles before each sector report is generated

### Requirement: Sector evidence preparation SHALL classify market evidence roles
The system SHALL classify market evidence into explicit roles so trend validation can distinguish exact sector evidence from alias or proxy evidence.

#### Scenario: Exact market evidence is direct evidence
- **WHEN** `market_sectors` contains a row matching the tracked sector's canonical identity
- **THEN** evidence collection SHALL classify that row as `exact_market`
- **AND** it SHALL count as direct market evidence for the sector

#### Scenario: Alias market evidence is direct when high confidence
- **WHEN** `market_sectors` contains a row matching an explicit alias or accepted equivalent identity of the tracked sector
- **THEN** evidence collection SHALL classify that row as `alias_market`
- **AND** high-confidence alias evidence SHALL be eligible to count as direct market evidence

#### Scenario: Proxy market evidence remains distinct from aliases
- **WHEN** `market_sectors` contains rows for related theme members or group proxy sectors but not the tracked sector itself
- **THEN** evidence collection SHALL classify those rows as `proxy_market`
- **AND** it SHALL NOT merge the proxy sector into the tracked sector identity

#### Scenario: No market evidence remains visible
- **WHEN** no exact, alias, or proxy market evidence is available
- **THEN** evidence diagnostics SHALL classify the market role as `no_market`
- **AND** the trend validation SHALL continue to apply conservative no-market constraints

### Requirement: Prepared evidence SHALL use confidence tiers
The system SHALL assign confidence tiers to prepared aliases, theme links, watch attribution, and market proxy evidence, and SHALL use those tiers to control downstream trend impact.

#### Scenario: High-confidence preparation can participate in trend judgement
- **WHEN** evidence preparation produces a high-confidence alias, theme link, or proxy market relationship
- **THEN** trend evidence collection SHALL include it with provenance
- **AND** validation MAY use it according to the supported evidence role rules

#### Scenario: Medium-confidence preparation remains weak evidence
- **WHEN** evidence preparation produces a medium-confidence relationship
- **THEN** trend evidence collection SHALL include it as weak or proxy evidence
- **AND** diagnostics SHALL distinguish it from direct evidence

#### Scenario: Low-confidence preparation does not promote stages
- **WHEN** evidence preparation produces only low-confidence matches for a sector
- **THEN** those matches SHALL NOT satisfy direct market evidence requirements
- **AND** they SHALL NOT by themselves promote a sector from `暂无趋势` to an active stage

### Requirement: Sector trend reports SHALL persist preparation diagnostics
The system SHALL persist evidence preparation diagnostics with sector trend summaries so users can audit why a sector was classified as active, proxy-backed, weak, or data-missing.

#### Scenario: Diagnostics show automatic preparation actions
- **WHEN** automatic evidence preparation runs before a sector trend update
- **THEN** the persisted evidence JSON SHALL include repaired watch counts, alias matches, theme matches, market evidence roles, proxy candidates, and low-confidence ignored counts where available

#### Scenario: Diagnostics distinguish proxy-backed activity
- **WHEN** a sector trend uses proxy market evidence
- **THEN** the persisted evidence JSON SHALL mark the evidence as proxy-backed
- **AND** it SHALL include the source proxy sectors or theme relationships where available

### Requirement: Sector validation SHALL remain conservative while accepting eligible prepared evidence
The system SHALL keep trend-stage validation conservative, but SHALL use prepared evidence roles so high-confidence alias or proxy-backed multi-source evidence is not treated as total market-data absence.

#### Scenario: High-confidence alias evidence satisfies market presence
- **WHEN** a sector has high-confidence alias market evidence and fresh watch or telegraph confirmation
- **THEN** validation MAY treat the sector as having usable market evidence
- **AND** it SHALL still enforce prior-context and sparse-evidence constraints

#### Scenario: Proxy evidence requires multi-source confirmation
- **WHEN** a sector lacks exact and alias market evidence but has proxy market evidence
- **THEN** validation SHALL require additional fresh watch or telegraph evidence before allowing an active stage
- **AND** proxy evidence alone SHALL NOT allow `主线加强`, `主线延续`, or `低位启动`

#### Scenario: Low-confidence evidence remains conservative
- **WHEN** a sector only has low-confidence prepared evidence
- **THEN** validation SHALL behave as if the sector lacks usable market evidence

### Requirement: Sector reports SHALL synchronize final validated labels
The system SHALL use the final post-validation sector labels consistently across Markdown reports, database summaries, CLI output, and downstream consumers.

#### Scenario: Validated label replaces AI raw label in Markdown
- **WHEN** AI generates a sector report with `trend_status: 主线加强`
- **AND** service validation downgrades the final sector label to `暂无趋势`
- **THEN** the saved Markdown report's authoritative structured label SHALL be `暂无趋势`
- **AND** the database summary `trend_status` SHALL also be `暂无趋势`

#### Scenario: Raw AI label is diagnostic only
- **WHEN** the system retains an AI-proposed label that differs from the final validated label
- **THEN** the raw label SHALL only appear in diagnostics or provenance
- **AND** history, matrix, group validation, and CLI result rows SHALL use the final validated label
