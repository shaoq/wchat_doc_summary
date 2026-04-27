## MODIFIED Requirements

### Requirement: System shall determine A-share trading days

The system SHALL correctly determine whether a given date is an A-share trading day, excluding weekends and Chinese statutory holidays, and SHALL use the most recent past trading day as the default `trade_date` when market summary is executed on a non-trading day or before the current trading day opens.

#### Scenario: Weekday determination
- **WHEN** user queries a regular weekday (e.g., 2026-03-23, Monday)
- **THEN** system returns that the date is a trading day

#### Scenario: Weekend determination
- **WHEN** user queries a weekend date (e.g., 2026-03-22, Sunday)
- **THEN** system returns that the date is not a trading day

#### Scenario: Holiday determination
- **WHEN** user queries a statutory holiday (e.g., 2026-01-01, New Year's Day)
- **THEN** system returns that the date is not a trading day

#### Scenario: Get most recent trading day
- **WHEN** current date is a non-trading day
- **THEN** system returns the most recent past trading day

#### Scenario: Use previous trading day before market open
- **WHEN** current date is a trading day
- **AND** market summary is executed before market open
- **THEN** system uses the previous trading day as the default `trade_date`

### Requirement: System shall generate market summary

The system SHALL generate a structured market summary report based on the selected `trade_date`, and the system SHALL collect different source materials using source-specific time windows derived from that `trade_date`.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the system SHALL determine a default `trade_date` before collecting source materials

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** the source-material windows SHALL be derived from that specified `trade_date`

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only cached articles, without fetching real-time market data

#### Scenario: Weekend execution uses latest trading day
- **WHEN** user executes `wchat ai market-summary` on a Saturday
- **THEN** the system SHALL use Friday as the default `trade_date`
- **AND** the source-material windows SHALL be derived from that Friday `trade_date`

## ADDED Requirements

### Requirement: CLS watch data uses an intraday trade-date window

The system SHALL collect CLS watch data for market summary using only the selected trade day's intraday window.

#### Scenario: Watch data for regular trading day
- **WHEN** market summary is generated for a trading day
- **THEN** the system fetches watch data from `trade_date 09:00` to `trade_date 15:00`

#### Scenario: Watch data for Friday before weekend
- **WHEN** market summary is generated for a Friday trading day
- **THEN** the system fetches watch data only from Friday `09:00` to Friday `15:00`

### Requirement: CLS telegraphs use a message-flow window from trade day to next trade day

The system SHALL collect CLS telegraphs for market summary using a window that covers the selected trade day's intraday important messages and extends to the next trading day's pre-open period.

#### Scenario: Telegraph window for regular trading day
- **WHEN** market summary is generated for a trading day
- **THEN** the system fetches telegraphs from `trade_date 09:00` to `next_trade_date 09:15`

#### Scenario: Telegraph window for Friday before weekend
- **WHEN** market summary is generated for a Friday trading day
- **THEN** the system fetches telegraphs from Friday `09:00` to Monday `09:15`

### Requirement: Articles use a post-close to next-trade-day window

The system SHALL collect related articles for market summary using a post-close window from the selected trade day to the next trading day's pre-open period.

#### Scenario: Article window for regular trading day
- **WHEN** market summary is generated for a trading day
- **THEN** the system fetches articles from `trade_date 15:00` to `next_trade_date 09:15`

#### Scenario: Article window for Friday before weekend
- **WHEN** market summary is generated for a Friday trading day
- **THEN** the system fetches articles from Friday `15:00` to Monday `09:15`

### Requirement: CLI displays source-specific material windows

The system SHALL display the effective material-collection windows in the CLI using the same source-specific windows that are used for querying.

#### Scenario: Display watch window
- **WHEN** market summary starts collecting CLS watch data
- **THEN** the CLI displays the effective watch-data window

#### Scenario: Display telegraph window
- **WHEN** market summary starts collecting CLS telegraphs
- **THEN** the CLI displays the effective telegraph window

#### Scenario: Display article window
- **WHEN** market summary starts collecting related articles
- **THEN** the CLI displays the effective article window
