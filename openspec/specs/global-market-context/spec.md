# global-market-context Specification

## Purpose
TBD - created by archiving change add-us-market-context-to-market-summary. Update Purpose after archive.
## Requirements
### Requirement: System SHALL collect structured overseas market context for A-share summary generation

The system SHALL be able to collect a normalized overseas market context payload for a target A-share trade date, with U.S. market signals as the default first-class scope.

#### Scenario: Online run collects U.S. market context
- **WHEN** `wchat ai market-summary` runs in online mode for a current target A-share trade date
- **THEN** the system SHALL attempt to collect a structured U.S. market context payload
- **AND** that payload SHALL include normalized index signals, risk signals, and source/status metadata

### Requirement: Overseas market context SHALL use explicit dual-time semantics

The system SHALL preserve separate fields for the A-share target trade date, system capture time, upstream market as-of time, and the detected U.S. market session.

#### Scenario: Context records target trade date separately from market timestamp
- **WHEN** the system stores or passes overseas market context for summary generation
- **THEN** it SHALL include `target_a_trade_date`
- **AND** it SHALL include `captured_at`
- **AND** it SHALL include `as_of`
- **AND** it SHALL include `session`

### Requirement: Overseas market context SHALL expose normalized quality states

The system SHALL expose an overall status and per-market status that distinguish successful, degraded, and failed overseas context outcomes.

#### Scenario: Partial overseas context remains consumable
- **WHEN** some required U.S. market signals are available but one or more configured signals fail to load
- **THEN** the overall overseas market context status SHALL be `partial`
- **AND** the available signals SHALL remain present in the payload
- **AND** missing signals SHALL NOT be fabricated with zero-value placeholders

#### Scenario: Failed overseas context is explicit
- **WHEN** the system cannot load any usable U.S. market context signals
- **THEN** the overseas market context status SHALL be `error`
- **AND** the payload SHALL expose enough metadata for downstream consumers to identify the failure

### Requirement: Overseas market context SHALL keep a focused first-phase signal set

The system SHALL limit first-phase structured overseas context to a curated set of signals with high explanatory value for next-session A-share interpretation.

#### Scenario: Payload includes prioritized signal categories
- **WHEN** the system successfully builds a first-phase U.S. market context payload
- **THEN** it SHALL include the three major U.S. equity indices
- **AND** it SHALL include configured risk signals such as volatility, dollar, or U.S. Treasury yield proxies
- **AND** it SHALL include at most a small configured set of sector or mega-cap leader proxy signals

