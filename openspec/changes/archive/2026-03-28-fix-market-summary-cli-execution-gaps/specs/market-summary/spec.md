## MODIFIED Requirements

### Requirement: System shall generate market summary
The system SHALL generate a structured market summary report based on unified market data, aggregated market news, and trade-date-related articles.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the selected trade date SHALL be passed through to the market data collection flow

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** the specified trade date SHALL be passed to market data collection instead of being ignored by the CLI layer

#### Scenario: Offline mode with local data
- **WHEN** user executes `wchat ai market-summary --offline` and local market data exists
- **THEN** system generates summary using only locally available market data, market news, and related articles
- **AND** the CLI SHALL not trigger online market data collection

#### Scenario: Offline mode without local data
- **WHEN** user executes `wchat ai market-summary --offline` and no local market data exists
- **THEN** the CLI SHALL clearly report that local market data is unavailable
- **AND** the CLI SHALL stop before AI summary generation

#### Scenario: Force refresh
- **WHEN** user executes `wchat ai market-summary --force`
- **THEN** system SHALL bypass reusable cached market data for the target trade date
- **AND** the `force` flag SHALL be passed from CLI to market data collection

### Requirement: Historical summaries can be listed
The system SHALL list saved historical market summaries through the CLI.

#### Scenario: List saved summaries
- **WHEN** user executes `wchat ai market-summary --list`
- **THEN** system SHALL display saved market summaries in reverse trade-date order
- **AND** each row SHALL show the trade date and the summary creation time
