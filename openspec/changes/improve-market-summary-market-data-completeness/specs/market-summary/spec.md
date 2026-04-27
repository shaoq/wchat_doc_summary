## ADDED Requirements

### Requirement: Market-summary consumes expanded sector context

The system SHALL expose expanded sector context to market-summary consumers, using twenty sector items composed of the top ten and bottom ten normalized sector rows when available.

#### Scenario: Stage 1 reports expanded sector count
- **WHEN** `wchat ai market-summary` renders market data status after sector data succeeds
- **THEN** the CLI SHALL be able to report the actual expanded sector count from the normalized market data payload
- **AND** the successful path SHALL no longer assume the sector contract is fixed at ten items

#### Scenario: AI summary input includes expanded sector context
- **WHEN** market-summary builds the market-data context for AI generation
- **THEN** it SHALL use the expanded top-ten and bottom-ten sector lists from the normalized payload
- **AND** it SHALL preserve the distinction between advancing and declining sector groups

### Requirement: Market-summary consumes full or fullest-available limit-up input

The system SHALL preserve the full or fullest-available normalized limit-up stock set for market-summary consumers, while allowing downstream presentation layers to apply their own display truncation without changing the underlying payload contract.

#### Scenario: Data layer preserves dedicated limit-up pool result
- **WHEN** the normalized market data payload contains a dedicated limit-up pool result set larger than twenty items
- **THEN** the market-summary data layer SHALL preserve that full result set
- **AND** downstream consumers SHALL NOT be forced to see only a top-20 subset from the data-layer contract

#### Scenario: Presentation layer truncates without altering payload semantics
- **WHEN** a CLI section or AI prompt chooses to display only part of the normalized limit-up stock set for readability
- **THEN** that truncation SHALL occur in the consuming layer
- **AND** it SHALL NOT change the underlying normalized market data payload size or semantics

### Requirement: Market-summary surfaces finer-grained breadth quality outcomes

The system SHALL expose enough normalized breadth-quality information for market-summary consumers to distinguish `ok`, `near-complete`, `partial`, and `error` outcomes for rise-fall statistics.

#### Scenario: Stage 1 distinguishes near-complete from partial
- **WHEN** `wchat ai market-summary` renders rise-fall statistics status
- **AND** the normalized breadth quality for statistics is `near-complete`
- **THEN** the CLI SHALL present it differently from a meaningfully incomplete `partial` result
- **AND** it SHALL preserve the actual and expected sample counts in the user-visible summary

#### Scenario: AI summary input receives quality-aware breadth metadata
- **WHEN** market-summary prepares market-data context for AI generation
- **THEN** it SHALL preserve the normalized breadth quality status for rise-fall statistics
- **AND** it SHALL allow the prompt-building layer to distinguish fully complete, near-complete, partial, and failed width data
