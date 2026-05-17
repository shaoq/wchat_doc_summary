## ADDED Requirements

### Requirement: Sector group trend updates SHALL support explicit report dates
The system SHALL allow sector group trend updates to generate or replay group reports for a specified trade date instead of always using the latest trade date.

#### Scenario: Single group update uses explicit date
- **WHEN** a user runs `wchat ai sector-trends groups update --group AI --date 2026-05-15`
- **THEN** the system SHALL use `2026-05-15` as the group report date
- **AND** it SHALL save the group report under the group path for `2026-05-15`

#### Scenario: Batch group update uses explicit date
- **WHEN** a user runs `wchat ai sector-trends groups update --all --date 2026-05-15`
- **THEN** the system SHALL update active groups using `2026-05-15` as the report date
- **AND** idempotency checks SHALL compare existing group summaries against `2026-05-15`

### Requirement: Group trend replay SHALL use date-appropriate member summaries
Group trend evidence SHALL prefer member sector summaries for the requested report date and SHALL mark missing or stale members explicitly.

#### Scenario: Member summary for target date is used
- **WHEN** a group member has a `SectorTrendSummary` for the requested report date
- **THEN** group evidence SHALL include that target-date member summary
- **AND** member freshness SHALL mark the member as current

#### Scenario: Member summary after target date is ignored
- **WHEN** a group member has a newer summary after the requested report date
- **AND** it has no summary for the requested report date or earlier acceptable date
- **THEN** group evidence SHALL NOT use the newer future summary
- **AND** member freshness SHALL mark the target-date evidence as missing or stale

#### Scenario: Sparse member reports downgrade group judgement
- **WHEN** multiple confirmed group members lack target-date trend summaries
- **THEN** the group trend report SHALL explicitly state the member evidence gap
- **AND** it SHALL use conservative observation language rather than strong group resonance claims
