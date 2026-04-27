## MODIFIED Requirements

### Requirement: Market summary can be saved and updated

The system SHALL support saving market summaries with upsert behavior:
- If no summary exists for the trade date, insert a new record
- If a summary already exists for the trade date, update the existing record's content and data_sources

#### Scenario: Save new market summary
- **WHEN** saving a market summary for a date that has no existing record
- **THEN** a new record SHALL be inserted with the provided content
- **AND** the record's created_at SHALL be set to the current timestamp

#### Scenario: Update existing market summary (upsert)
- **WHEN** saving a market summary for a date that already has a record
- **THEN** the existing record's content and data_sources SHALL be updated
- **AND** the record's created_at SHALL NOT be changed
- **AND** no UNIQUE constraint error SHALL occur

#### Scenario: Force regenerate with --force flag
- **WHEN** user runs `wchat ai market-summary --force` for a date with existing summary
- **THEN** the existing summary SHALL be overwritten with new content
- **AND** the command SHALL complete successfully without database errors
