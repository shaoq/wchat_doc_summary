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
## Requirements
### Requirement: Market-summary SHALL expose fallback-aware overseas market context status

The system SHALL provide enough normalized overseas market context metadata for `market-summary` CLI output and AI prompt generation to distinguish primary success, fallback success, and total upstream failure.

#### Scenario: CLI shows fallback success semantics
- **WHEN** stage 1 of `wchat ai market-summary` renders a partially degraded but usable overseas market context
- **THEN** the CLI SHALL be able to communicate that the primary provider failed
- **AND** it SHALL be able to communicate which fallback provider supplied the final usable context

#### Scenario: Prompt blocks inference on upstream authorization failure
- **WHEN** all overseas market context providers fail and the terminal failure type is `unauthorized`
- **THEN** the AI input contract SHALL preserve that failure type in structured form
- **AND** the prompt gap instructions SHALL tell the model not to infer overnight U.S. market behavior from missing signals

### Requirement: Market-summary SHALL consume overseas market context as a dedicated evidence group

The system SHALL pass overseas market context to market-summary generation as a dedicated structured evidence group rather than merging it into A-share market data or free-form news text.

#### Scenario: AI generation receives overseas context separately
- **WHEN** `AIProcessor.generate_market_summary()` prepares the summary prompt
- **THEN** the prompt-building flow SHALL receive overseas market context as a separate structured input
- **AND** the prompt template SHALL be able to render that input independently from A-share market data, CLS data, and articles

### Requirement: Market-summary CLI SHALL expose overseas context status in stage 1

The system SHALL present overseas market context collection outcomes as part of the stage-1 market-data summary for `market-summary`.

#### Scenario: Stage 1 shows overseas context metadata
- **WHEN** stage 1 of `wchat ai market-summary` finishes with an overseas market context result
- **THEN** the CLI SHALL be able to display the overseas context status
- **AND** it SHALL be able to display the detected market session and as-of time when available
- **AND** it SHALL preserve the existing three-stage command structure

### Requirement: Market-summary SHALL not infer missing overseas signals

The system SHALL preserve explicit data-gap semantics for overseas market context so that summary generation can acknowledge missing data without inventing unobserved overseas moves.

#### Scenario: Prompt marks overseas context as unavailable
- **WHEN** overseas market context is `partial` or `error`
- **THEN** the prompt input SHALL explicitly indicate that the overseas signal set is incomplete or unavailable
- **AND** the summary generation flow SHALL be able to continue without treating missing overseas signals as known facts

### Requirement: Historical and offline summaries SHALL use cached overseas context only

The system SHALL treat overseas market context as a replayable summary input and SHALL NOT auto-fetch replacement overseas context for historical or offline summary runs.

#### Scenario: Historical summary replays cached overseas context
- **WHEN** the user generates `market-summary` for a historical trade date
- **AND** cached overseas market context exists for that target trade date
- **THEN** the system SHALL use the cached overseas context in summary generation

#### Scenario: Offline summary does not fetch overseas context
- **WHEN** the user runs `wchat ai market-summary --offline`
- **THEN** the system SHALL NOT trigger any overseas market context network fetch
- **AND** it SHALL only use locally available overseas context data if present

### Requirement: Market-summary stage output reflects final market data status

The market-summary command SHALL present market data collection status based on final normalized outcomes, not intermediate recoverable source-attempt failures.

#### Scenario: recoverable market data attempts succeed through fallback
- **WHEN** `wchat ai market-summary` collects market data
- **AND** one or more upstream attempts fail but fallback or later hosts produce usable data
- **THEN** stage 1 SHALL display the final successful, near-complete, or fallback status
- **AND** stage 1 SHALL NOT present the recoverable attempt failure as the primary market data outcome

#### Scenario: market data source category is finally unavailable
- **WHEN** `wchat ai market-summary` collects market data
- **AND** all configured upstreams for a market data category fail
- **THEN** stage 1 SHALL display the normalized error or degraded status for that category
- **AND** the logs SHALL include a single final failure summary for that category rather than multiple recoverable attempt warnings

