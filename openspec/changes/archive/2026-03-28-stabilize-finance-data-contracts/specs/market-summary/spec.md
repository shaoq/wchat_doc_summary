## MODIFIED Requirements

### Requirement: System shall generate market summary
The system SHALL generate a structured market summary report based on unified market data, aggregated market news, and trade-date-related articles.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the market overview input SHALL be consumed from the normalized finance data contract rather than source-specific field variants

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** the system SHALL use the normalized finance data contract for that trade date

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only locally available market data, market news, and related articles
- **AND** the local market data payload SHALL follow the same normalized finance data contract used online

#### Scenario: Force refresh
- **WHEN** user executes `wchat ai market-summary --force`
- **THEN** system SHALL bypass reusable cached market data for the target trade date
- **AND** the freshly collected market data SHALL still follow the normalized finance data contract
