## MODIFIED Requirements

### Requirement: System shall determine A-share trading days

The system SHALL correctly determine whether a given date is an A-share trading day, excluding weekends and Chinese statutory holidays, and SHALL use the most recent past trading day as the default `trade_date` when market summary is executed on a non-trading day.

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

#### Scenario: Weekend default summary date
- **WHEN** user executes `wchat ai market-summary` on a Saturday
- **THEN** the system SHALL use Friday as the default `trade_date`

### Requirement: System shall generate market summary

The system SHALL generate a structured market summary report based on template format, and SHALL stop before AI generation when market data collection reports that required market data is unavailable.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only cached articles, without fetching real-time market data

#### Scenario: Market data unavailable stops generation
- **WHEN** market data collection returns an explicit unavailable state for the selected trade date
- **THEN** the CLI SHALL clearly report the failure
- **AND** the CLI SHALL stop before news aggregation and AI summary generation
