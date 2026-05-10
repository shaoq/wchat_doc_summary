## ADDED Requirements

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
