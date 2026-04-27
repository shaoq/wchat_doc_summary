## MODIFIED Requirements

### Requirement: Skip only successfully processed articles
The system SHALL skip only articles with `status='success'` when checking for processed articles. Articles with `status='failed'` SHALL be reprocessed.

#### Scenario: Skip successfully processed articles
- **WHEN** batch processing articles without force flag
- **THEN** articles with `status='success'` for the given task type SHALL be skipped

#### Scenario: Retry failed articles
- **WHEN** batch processing articles without force flag
- **THEN** articles with `status='failed'` for the given task type SHALL be reprocessed

#### Scenario: Force reprocess all articles
- **WHEN** batch processing articles with force flag set to true
- **THEN** all articles SHALL be reprocessed regardless of status
