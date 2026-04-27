## MODIFIED Requirements

### Requirement: System shall generate market summary

The system SHALL generate a structured market summary report based on a single selected trade date, and in realtime mode the market data items used by the summary SHALL stay aligned to that selected date when it is today or the most recent completed trading day.

#### Scenario: Auto-generate summary
- **WHEN** user executes `wchat ai market-summary` command
- **THEN** system generates a summary containing market overview and market news
- **AND** the selected trade date SHALL be used consistently across the realtime market-data items in the summary input

#### Scenario: Generate for specific date
- **WHEN** user executes `wchat ai market-summary --date 2026-03-21`
- **THEN** system generates market summary for the specified date
- **AND** if that date is the most recent completed trading day, date-sensitive realtime market data items SHALL align to that selected trade date instead of blindly using system-today semantics

#### Scenario: Offline mode
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** system generates summary using only cached articles, without fetching real-time market data
