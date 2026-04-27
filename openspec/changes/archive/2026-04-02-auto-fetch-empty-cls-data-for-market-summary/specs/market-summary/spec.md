## ADDED Requirements

### Requirement: Market-summary online mode auto-fetches empty CLS telegraph data

The system SHALL automatically fetch CLS telegraph data for the market-summary telegraph window when online mode finds no local telegraph data for that window, and SHALL re-query local storage before deciding the final source status.

#### Scenario: Local telegraph cache hit skips auto-fetch
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS telegraph data already exists for the summary telegraph window
- **THEN** the system SHALL use the local telegraph data directly
- **AND** it SHALL NOT trigger an additional telegraph fetch for that source

#### Scenario: Local telegraph cache miss auto-fetches and succeeds
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS telegraph data is empty for the summary telegraph window
- **AND** the automatic telegraph fetch succeeds and local re-query returns telegraph records
- **THEN** the final telegraph source status SHALL be `ok`
- **AND** the telegraph records SHALL be included in the news payload used for summary generation

#### Scenario: Local telegraph cache miss auto-fetches but still remains empty
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS telegraph data is empty for the summary telegraph window
- **AND** the automatic telegraph fetch completes without fetch error
- **AND** the local re-query still returns no telegraph records
- **THEN** the final telegraph source status SHALL be `empty`
- **AND** the CLI SHALL be able to communicate that automatic fetch was attempted

#### Scenario: Local telegraph cache miss auto-fetch fails
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS telegraph data is empty for the summary telegraph window
- **AND** the automatic telegraph fetch fails
- **THEN** the final telegraph source status SHALL be `error`
- **AND** the CLI SHALL report telegraph fetch failure instead of a plain `0 条`

### Requirement: Market-summary online mode auto-fetches empty CLS watch data

The system SHALL automatically fetch CLS watch data for the market-summary watch window when online mode finds no local watch data for that window, and SHALL re-query local storage before deciding the final source status.

#### Scenario: Local watch cache hit skips auto-fetch
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS watch data already exists for the summary watch window
- **THEN** the system SHALL use the local watch data directly
- **AND** it SHALL NOT trigger an additional watch fetch for that source

#### Scenario: Local watch cache miss auto-fetches and succeeds
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS watch data is empty for the summary watch window
- **AND** the automatic watch fetch succeeds and local re-query returns watch records
- **THEN** the final watch source status SHALL be `ok`
- **AND** the watch records SHALL be included in the news payload used for summary generation

#### Scenario: Local watch cache miss auto-fetches but still remains empty
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS watch data is empty for the summary watch window
- **AND** the automatic watch fetch completes without fetch error
- **AND** the local re-query still returns no watch records
- **THEN** the final watch source status SHALL be `empty`
- **AND** the CLI SHALL be able to communicate that automatic fetch was attempted

#### Scenario: Local watch cache miss auto-fetch fails
- **WHEN** `wchat ai market-summary` runs in online mode
- **AND** local CLS watch data is empty for the summary watch window
- **AND** the automatic watch fetch fails
- **THEN** the final watch source status SHALL be `error`
- **AND** the CLI SHALL report watch fetch failure instead of a plain `0 条`

### Requirement: Offline market-summary must not auto-fetch CLS data

The system SHALL preserve offline mode as a local-only execution path even when CLS telegraph or watch data is empty.

#### Scenario: Offline mode leaves empty CLS sources untouched
- **WHEN** the user runs `wchat ai market-summary --offline`
- **AND** local CLS telegraph data or local CLS watch data is empty
- **THEN** the system SHALL NOT trigger automatic CLS fetch for those sources
- **AND** the final source status SHALL continue to reflect only local availability

### Requirement: CLI exposes auto-fetch-aware CLS source outcomes

The system SHALL expose enough normalized status information for the CLI to distinguish direct local hit, auto-fetch success, auto-fetch-empty, and auto-fetch failure outcomes for CLS telegraph and watch sources.

#### Scenario: Stage 2 shows auto-fetch-aware CLS status
- **WHEN** stage 2 of `wchat ai market-summary` renders CLS source statuses
- **THEN** the CLI SHALL be able to tell the user whether a CLS source was satisfied from local data, was auto-fetched successfully, remained empty after auto-fetch, or failed during auto-fetch
- **AND** it SHALL preserve the existing normalized final status semantics of `ok`, `empty`, or `error`
