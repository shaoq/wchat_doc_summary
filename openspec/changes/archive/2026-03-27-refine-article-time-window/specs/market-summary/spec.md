## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Display time window in CLI output
The system SHALL display the calculated time window when generating market summary in the CLI.

#### Scenario: Show time window in console output
- **WHEN** running `wchat ai market-summary`
- **THEN** console displays "时间窗口: {start} ~ {end}" before fetching articles

#### Scenario: Format time window as human readable
- **WHEN** displaying time window
- **THEN** times are formatted as "YYYY-MM-DD HH:MM"
