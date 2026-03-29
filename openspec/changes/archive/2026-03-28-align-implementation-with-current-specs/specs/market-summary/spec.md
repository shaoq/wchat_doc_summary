## MODIFIED Requirements

### Requirement: System shall determine A-share trading days

The system SHALL correctly determine whether a given date is an A-share trading day by excluding weekends and Chinese statutory holidays, and SHALL NOT treat weekend make-up workdays as trading days.

#### Scenario: Weekday determination
- **WHEN** user queries a regular weekday (e.g., 2026-03-23, Monday)
- **THEN** system returns that the date is a trading day

#### Scenario: Weekend determination
- **WHEN** user queries a weekend date (e.g., 2026-03-22, Sunday)
- **THEN** system returns that the date is not a trading day

#### Scenario: Holiday determination
- **WHEN** user queries a statutory holiday (e.g., 2026-01-01, New Year's Day)
- **THEN** system returns that the date is not a trading day

#### Scenario: Make-up workday weekend is not treated as trading day
- **WHEN** user queries a weekend date that is a make-up workday in the general holiday calendar
- **THEN** system returns that the date is not a trading day for A-share summary generation

#### Scenario: Get most recent trading day
- **WHEN** current date is a non-trading day
- **THEN** system returns the most recent past trading day

### Requirement: System shall generate market summary

The system SHALL generate a structured market summary report based on the selected trade date, and all market data used for the summary SHALL correspond to that same target trade date.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the selected trade date SHALL be used as the basis for market data, news aggregation, and article selection

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** the system SHALL NOT substitute current-day market data for the specified historical trade date

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only locally available market data, market news, and related articles
- **AND** the system SHALL NOT fetch real-time market data over the network

#### Scenario: Historical date without valid market data
- **WHEN** user executes market summary generation for a historical trade date
- **AND** no market data aligned to that trade date is available from cache or a supported historical source
- **THEN** the system SHALL clearly report that market data for the target trade date is unavailable
- **AND** the system SHALL stop before generating a summary with mismatched current-day data

### Requirement: Get related articles for market summary

The system SHALL fetch articles published within the precise trading time window (trade_date 15:00 to next_trading_date 09:15), replacing the previous days_back approach.

#### Scenario: Fetch articles for standard trading day
- **WHEN** market summary is generated for a Tuesday trading day
- **THEN** system fetches articles from Tuesday 15:00 to Wednesday 09:15

#### Scenario: Fetch articles for Friday before weekend
- **WHEN** market summary is generated for a Friday trading day
- **THEN** system fetches articles from Friday 15:00 to Monday 09:15

#### Scenario: Fetch articles for pre-holiday trading day
- **WHEN** market summary is generated for a trading day before a holiday
- **THEN** system fetches articles from that day 15:00 to the first trading day after holiday 09:15

#### Scenario: Log time window during article fetch
- **WHEN** fetching articles for market summary
- **THEN** system logs the calculated time window start and end times

#### Scenario: Query and display use the same time window
- **WHEN** the system displays the effective article time window in CLI output
- **THEN** the displayed start and end times SHALL match the actual query window used for article selection

### Requirement: Display time window in CLI output

The system SHALL display the calculated time window when generating market summary in the CLI.

#### Scenario: Show time window in console output
- **WHEN** running `wchat ai market-summary`
- **THEN** console displays "时间窗口: {start} ~ {end}" using the actual article query window

#### Scenario: Format time window as human readable
- **WHEN** displaying time window
- **THEN** times are formatted as "YYYY-MM-DD HH:MM"
