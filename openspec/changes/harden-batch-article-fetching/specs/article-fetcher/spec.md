## ADDED Requirements

### Requirement: Suspicious empty first-page results are retried before being treated as empty
The system SHALL treat an empty first-page article list response as suspicious in default batch and incremental synchronization paths, and it SHALL perform a bounded retry sequence before concluding that no articles are available.

#### Scenario: First-page empty result is retried
- **WHEN** the first page of an article list request returns an empty article list in a path that expects recent articles
- **THEN** the system SHALL retry the same page within a bounded number of attempts
- **AND** it SHALL apply retry pacing before deciding the page is truly empty

#### Scenario: Repeated suspicious empty result is classified explicitly
- **WHEN** every bounded retry for a suspicious empty first-page result still returns empty
- **THEN** the system SHALL classify the fetch outcome as an explicit empty-result state
- **AND** it SHALL preserve that classification for logs or CLI reporting

### Requirement: Invalid list responses do not silently degrade to empty article lists
The system SHALL reject invalid article-list response payloads instead of silently converting them into empty article lists.

#### Scenario: Non-dict response is treated as list-response failure
- **WHEN** an article-list provider client receives a payload that does not match the expected response structure
- **THEN** the system SHALL raise or surface a list-response failure
- **AND** it SHALL NOT normalize that payload into a successful `0`-article response

### Requirement: Batch and single-feed fetch reporting distinguishes empty, existing, inserted, and failed outcomes
The system SHALL expose fetch-result reporting that distinguishes upstream-empty results, already-existing articles, newly inserted articles, and article-save failures.

#### Scenario: Existing articles produce zero inserts without appearing as empty upstream
- **WHEN** an article list request returns articles but every candidate article already exists locally
- **THEN** the system SHALL report zero inserted articles
- **AND** it SHALL preserve that the upstream list was non-empty in the fetch summary

#### Scenario: Mixed insert and failure outcomes are preserved in summary
- **WHEN** a fetch run receives a non-empty article list and only part of the articles are saved successfully
- **THEN** the system SHALL report both the inserted count and the failed count
- **AND** it SHALL NOT collapse the result into a single ambiguous `0`-or-`N` outcome

### Requirement: Suspicious or failed list fetches do not advance sync time
The system SHALL update a feed's sync time only after a fetch path reaches a successful terminal state, and it SHALL NOT advance sync time for suspicious-empty or invalid-list outcomes.

#### Scenario: Invalid list response does not update sync time
- **WHEN** a fetch run ends because the article list response is invalid
- **THEN** the system SHALL leave `feeds.sync_time` unchanged

#### Scenario: Exhausted suspicious-empty retries do not update sync time
- **WHEN** a fetch run ends after bounded suspicious-empty retries are exhausted without a confirmed successful list result
- **THEN** the system SHALL leave `feeds.sync_time` unchanged
