## ADDED Requirements

### Requirement: Batch fetch default mode uses conservative incremental synchronization
The system SHALL treat `wchat fetch --all` without explicit `--days` or `--full` options as a conservative batch incremental synchronization flow rather than the single-feed newest-10 flow.

#### Scenario: Batch fetch defaults to incremental sync
- **WHEN** the user runs `wchat fetch --all` without `--days` and without `--full`
- **THEN** the system SHALL synchronize each subscribed feed using the incremental fetch path when local article history exists
- **AND** it SHALL NOT request the newest 10 articles for every feed by default

#### Scenario: Batch fetch falls back for uninitialized feed
- **WHEN** the user runs `wchat fetch --all` for a subscribed feed that has no stored articles yet
- **THEN** the system SHALL fall back to a bounded initialization fetch for that feed
- **AND** it SHALL keep the batch synchronization in the conservative path for other initialized feeds

### Requirement: Batch fetch applies proactive pacing between feeds
The system SHALL apply proactive pacing between subscribed feeds during batch fetch so that request frequency is reduced before an upstream rate limit is triggered.

#### Scenario: Normal batch pacing
- **WHEN** `fetch_all()` finishes one subscribed feed and proceeds to the next
- **THEN** the system SHALL wait for a bounded interval before issuing the next feed's list request
- **AND** the wait behavior SHALL be part of the batch fetch path rather than an operator convention

#### Scenario: Error-aware backoff during batch pacing
- **WHEN** a subscribed feed finishes with a transient fetch failure or suspicious empty-page retry exhaustion
- **THEN** the system SHALL apply a longer backoff before the next subscribed feed
- **AND** it SHALL continue to honor global rate-limit circuit breaking when a `RateLimitError` occurs

