## ADDED Requirements

### Requirement: System can backfill publish time for existing articles
The system SHALL provide a method to update publish_time for articles where it is NULL.

#### Scenario: Auto backfill after fetch
- **WHEN** fetch completes for a subscription
- **THEN** system updates publish_time for articles where publish_time IS NULL

#### Scenario: Manual backfill command
- **WHEN** user runs `wchat backfill <mp_id>`
- **THEN** system updates publish_time for all articles with NULL publish_time in that subscription

### Requirement: Backfill handles API errors gracefully
The system SHALL continue processing when individual article API calls fail.

#### Scenario: API call fails for one article
- **WHEN** publish_time API call fails for one article
- **THEN** system logs the error and continues to next article
