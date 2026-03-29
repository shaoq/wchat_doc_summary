## MODIFIED Requirements

### Requirement: System shall generate market summary
The system SHALL generate a structured market summary report based on unified market data, aggregated market news, and trade-date-related articles.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the summary input SHALL include unified market data and related market news for the selected trade date

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** the system SHALL use the specified trade date as the basis for market data, news aggregation, and article selection

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only locally available market data, market news, and related articles
- **AND** the system SHALL NOT fetch real-time market data over the network

#### Scenario: Force refresh
- **WHEN** user executes `wchat ai market-summary --force`
- **THEN** system SHALL bypass reusable cached market data for the target trade date
- **AND** the summary SHALL be generated from freshly collected online data when online mode is used

## ADDED Requirements

### Requirement: Historical summaries can be listed
The system SHALL list saved historical market summaries through the CLI.

#### Scenario: List saved summaries
- **WHEN** user executes `wchat ai market-summary --list`
- **THEN** system SHALL display saved market summaries in reverse trade-date order
- **AND** each row SHALL show the trade date and the summary creation time

### Requirement: Related articles use a trade-date-aware time window
The system SHALL select related articles for market summary generation using a trade-date-aware time window instead of a fixed day-count rollback.

#### Scenario: Article selection for trade date
- **WHEN** the system collects related articles for a trade date
- **THEN** it SHALL use a deterministic time window derived from the target trade date
- **AND** it SHALL exclude articles that fall outside that time window even if they are within a generic recent-days range

#### Scenario: CLI reports article window
- **WHEN** market summary generation displays article collection progress
- **THEN** the system SHALL be able to report the effective article time window used for the selected trade date
