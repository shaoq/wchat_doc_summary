## ADDED Requirements

### Requirement: Sector trend updates SHALL support explicit report dates
The system SHALL allow sector trend updates to generate or replay reports for a specified trade date instead of always using the latest trade date.

#### Scenario: Single sector update uses explicit date
- **WHEN** a user runs `wchat ai sector-trends update --sector 半导体 --date 2026-05-15`
- **THEN** the system SHALL collect evidence ending on `2026-05-15`
- **AND** it SHALL save the report under the sector path for `2026-05-15`

#### Scenario: Batch sector update uses explicit date
- **WHEN** a user runs `wchat ai sector-trends update --all --date 2026-05-15`
- **THEN** the system SHALL update tracked sectors using `2026-05-15` as the report date
- **AND** idempotency checks SHALL compare existing summaries against `2026-05-15`

### Requirement: Sector trend evidence SHALL expose historical data gaps
Sector trend evidence collection SHALL surface missing historical market data and insufficient CLS/watch evidence so AI generation can downgrade confidence.

#### Scenario: Missing market-sector cache is explicit
- **WHEN** the evidence window has no matching `MarketSector` rows for the sector
- **THEN** the evidence payload SHALL mark the market-sector evidence gap
- **AND** the generated trend report SHALL use conservative observation language

#### Scenario: Backfilled evidence supports trend replay
- **WHEN** market-sector cache and CLS watch data exist for the requested historical window
- **THEN** sector trend update SHALL include those records in the evidence payload for that explicit report date
- **AND** it SHALL NOT use records after the requested report date

### Requirement: Sector trend evidence SHALL include CLS telegraph mentions when available
The system SHALL use stored CLS telegraph records as an additional evidence source for sector trend generation when relevant mentions can be matched.

#### Scenario: Matching telegraph mention is included
- **WHEN** a stored CLS telegraph within the evidence window mentions the tracked sector name or alias
- **THEN** the sector evidence payload SHALL include that telegraph mention
- **AND** the evidence count SHALL reflect the additional mention

#### Scenario: No matching telegraph mention remains explicit
- **WHEN** no stored CLS telegraph within the evidence window matches the tracked sector
- **THEN** the evidence payload SHALL keep `cls_telegraph_mentions` empty
- **AND** the data gap summary SHALL identify missing telegraph evidence when other evidence is sparse
