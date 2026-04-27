## MODIFIED Requirements

### Requirement: System shall display market data summary (modified)

The system SHALL display the resolved width-data source outcome without implying that rise-fall statistics can still succeed through the removed AKShare fallback path.

#### Scenario: Show primary rise-fall statistics source outcome
- **WHEN** stage 1 renders width-data source information for `market-summary`
- **THEN** the CLI SHALL be able to indicate that rise-fall statistics came from `pytdx` when that primary source succeeds
- **AND** it SHALL continue to distinguish degraded or empty-value outcomes

#### Scenario: Do not expose removed statistics fallback label
- **WHEN** rise-fall statistics degrade because `pytdx` is partial or error
- **THEN** stage 1 output SHALL NOT claim that statistics were rescued by the removed AKShare fallback path
- **AND** the CLI SHALL NOT display a “涨跌统计旧链路兜底” source outcome for that run
