## RENAMED Requirements

### Requirement: List subscriptions command
The system SHALL provide a command to list all subscriptions.

FROM: `wchat list`
TO: `wchat ls`

#### Scenario: List all subscriptions
- **WHEN** user runs `wchat ls`
- **THEN** system displays a table of subscriptions with ID, name, mp_id, article count, latest article date, status, and last sync time

#### Scenario: List active subscriptions only
- **WHEN** user runs `wchat ls --active-only`
- **THEN** system displays only active subscriptions
