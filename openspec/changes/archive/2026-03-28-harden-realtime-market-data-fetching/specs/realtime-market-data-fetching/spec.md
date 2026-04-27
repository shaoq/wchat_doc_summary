## ADDED Requirements

### Requirement: Realtime market breadth snapshot is reused within one aggregation

The system SHALL fetch the full realtime stock snapshot at most once per market-data aggregation run when multiple derived metrics depend on the same snapshot.

#### Scenario: Volume and statistics share one stock snapshot
- **WHEN** the system collects realtime market data for a summary run
- **AND** both成交额 and涨跌统计 depend on the all-stock snapshot
- **THEN** the system SHALL fetch the all-stock snapshot once
- **AND** it SHALL derive both metrics from that same snapshot

### Requirement: Realtime market data aligns to the selected current or recent trade date

The system SHALL ensure that realtime market data items used for summary generation align to the selected trade date when that date is today or the most recent completed trading day.

#### Scenario: Current trading day uses current realtime data
- **WHEN** the selected trade date is today
- **THEN** the system SHALL collect realtime market data from current realtime sources

#### Scenario: Recent completed trade date does not mix in system-today-only data
- **WHEN** the selected trade date is the most recent completed trading day
- **THEN** each realtime-derived market data item SHALL use that selected trade date or cached data aligned to it
- **AND** the system SHALL NOT silently substitute a system-today-only payload for a date-sensitive item

### Requirement: Realtime fetch path uses effective retry and short-lived reuse

The system SHALL apply bounded retry behavior for transient external fetch failures and MAY reuse very recent in-memory realtime results within a short TTL window.

#### Scenario: Transient fetch failure is retried
- **WHEN** an external realtime market-data source fails transiently
- **THEN** the system SHALL retry the fetch up to the configured retry limit before returning failure or degraded data

#### Scenario: Repeated fetch within TTL reuses recent snapshot
- **WHEN** the same realtime market-data snapshot is requested repeatedly within the configured short TTL window
- **THEN** the system SHALL be able to reuse the recent in-memory snapshot instead of refetching it immediately
