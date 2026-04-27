## MODIFIED Requirements

### Requirement: Article fetcher supports full and incremental fetching
The system SHALL support both full fetching and incremental fetching for a subscribed公众号, and both modes SHALL share the same article persistence path.

#### Scenario: Full fetch for a subscription
- **WHEN** the system performs a full fetch for a subscribed `mp_id`
- **THEN** it SHALL retrieve article list pages from the upstream API
- **AND** it SHALL fetch and persist each eligible article through the shared article save path

#### Scenario: Incremental fetch for a subscription
- **WHEN** the system performs an incremental fetch for a subscribed `mp_id`
- **THEN** it SHALL compare upstream article publish times against the latest persisted article publish time for that subscription
- **AND** it SHALL only fetch articles newer than the latest persisted article

### Requirement: Article fetcher applies deterministic recent-article filtering
The system SHALL apply recent-article filtering using parsed publish times and a single cutoff comparison rule.

#### Scenario: Skip article older than cutoff
- **WHEN** the system fetches articles with a recent-days cutoff
- **THEN** any article whose parsed publish time is earlier than the cutoff SHALL be skipped
- **AND** the skipped article SHALL NOT be persisted as part of that recent fetch

#### Scenario: Stop paging when current page is fully older than cutoff
- **WHEN** the system evaluates a fetched article list page and every article with a parseable publish time is earlier than the cutoff
- **THEN** the system SHALL stop requesting subsequent pages for that recent fetch

### Requirement: Article fetcher resolves公众号信息 from article URL
The system SHALL resolve subscription metadata from an article URL through a dedicated公众号信息解析 path.

#### Scenario: Resolve subscription info from article URL
- **WHEN** the user provides a valid公众号 article URL
- **THEN** the system SHALL return a normalized dictionary containing `mp_id`, `name`, `intro`, and `cover` when available

#### Scenario: Upstream metadata response is invalid
- **WHEN** the upstream公众号 metadata response is not a valid dictionary or lacks both `mp_id` and `name`
- **THEN** the system SHALL fail the metadata resolution request with a validation error

## ADDED Requirements

### Requirement: Fetch workflow uses consistent error handling for article persistence
The system SHALL keep fetch-list retrieval, article content retrieval, and article persistence failures isolated per article whenever possible.

#### Scenario: Single article fetch fails during page processing
- **WHEN** one article fails during content fetch or save
- **THEN** the system SHALL continue processing remaining articles on the same fetch run
- **AND** the failed article SHALL be reported through logging
