## MODIFIED Requirements

### Requirement: Article fetch saves publish time
The system SHALL save article publish time when fetching articles.

#### Scenario: API returns publish_time
- **WHEN** WeRead API response contains `publish_time` field
- **THEN** system saves the publish time to database

#### Scenario: API has no publish_time, HTML has it
- **WHEN** WeRead API response lacks `publish_time` but HTML parsing succeeds
- **THEN** system uses parsed publish time as fallback

#### Scenario: Both sources lack publish_time
- **WHEN** neither API nor HTML provides publish time
- **THEN** system saves `NULL` for publish_time field
