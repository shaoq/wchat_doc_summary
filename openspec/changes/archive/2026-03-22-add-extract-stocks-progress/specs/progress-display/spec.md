## ADDED Requirements

### Requirement: Progress bar display for batch processing
The system SHALL display a progress bar when processing multiple articles.

#### Scenario: Progress bar shows current progress
- **WHEN** batch processing N articles
- **THEN** the system SHALL display a progress bar with current progress (M/N)

#### Scenario: Progress bar shows current article title
- **WHEN** processing an article
- **THEN** the system SHALL display the current article title being processed

#### Scenario: Progress bar shows statistics
- **WHEN** batch processing articles
- **THEN** the system SHALL display real-time statistics (success/skipped/failed counts)
