## ADDED Requirements

### Requirement: List all extracted stocks
The system SHALL provide a command to list all extracted stocks with their occurrence count.

#### Scenario: List stocks sorted by occurrence
- **WHEN** user runs `wchat ai stocks list`
- **THEN** the system SHALL display all stocks sorted by occurrence count in descending order

#### Scenario: List stocks for specific public account
- **WHEN** user runs `wchat ai stocks list --mp-id <mp_id>`
- **THEN** the system SHALL display stocks only from the specified public account

### Requirement: Search stocks by keyword
The system SHALL provide a command to search stocks by keyword.

#### Scenario: Search stocks by partial name
- **WHEN** user runs `wchat ai stocks search <keyword>`
- **THEN** the system SHALL display all stocks containing the keyword and their occurrence count

### Requirement: Show stock details
The system SHALL provide a command to show which articles contain a specific stock.

#### Scenario: Show articles containing a stock
- **WHEN** user runs `wchat ai stocks show <stock_name>`
- **THEN** the system SHALL display all articles that contain the stock, with article title and publish date
