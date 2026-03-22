## MODIFIED Requirements

### Requirement: Article fetch saves publish time
The system SHALL save article publish time when fetching articles, using the correct field name from API response.

#### Scenario: API returns publishTime (camelCase)
- **WHEN** WeRead API response contains `publishTime` field (camelCase)
- **THEN** system parses and saves the publish time

#### Scenario: API returns publish_time (snake_case)
- **WHEN** WeRead API response contains `publish_time` field (snake_case)
- **THEN** system parses and saves the publish time

#### Scenario: API has no publish time,- **WHEN** WeRead API response lacks both `publishTime` and `publish_time`
- **THEN** system falls back to HTML parsing result
