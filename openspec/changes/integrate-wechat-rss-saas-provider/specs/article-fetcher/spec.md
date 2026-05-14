## ADDED Requirements

### Requirement: RSS-backed article import is cache-first
The article fetch pipeline SHALL prefer feed-provided content for RSS-backed articles and avoid direct WeChat article-page fetching when the configured RSS content mode does not allow it.

#### Scenario: Feed item includes HTML content
- **WHEN** an RSS-backed provider article includes HTML content
- **THEN** the system SHALL import that content without requesting the original article page
- **AND** the article SHALL still be deduplicated and persisted through the normal article storage path

#### Scenario: Feed-only mode with missing content
- **WHEN** `rss_content_mode` is `feed_only` and an RSS-backed provider article lacks full content
- **THEN** the system SHALL NOT request the original article page
- **AND** it SHALL persist the available feed summary or mark the article content as unavailable without failing the whole subscription fetch

#### Scenario: Prefer-feed mode with missing content
- **WHEN** `rss_content_mode` is `prefer_feed` and an RSS-backed provider article lacks usable content
- **THEN** the system MAY request the original article page to fill missing content
- **AND** that direct request SHALL remain subject to existing fetch throttling and error handling

### Requirement: RSS-backed articles deduplicate by provider item and original URL
The article fetch pipeline SHALL deduplicate RSS-backed articles using provider item identity and original URL before inserting new article records.

#### Scenario: Same RSS item fetched twice
- **WHEN** the same RSS item appears in multiple fetch runs with the same provider item identity
- **THEN** the system SHALL detect the existing article
- **AND** it SHALL NOT insert a duplicate article

#### Scenario: RSS item identity changes but URL remains stable
- **WHEN** an RSS item has a changed GUID but the original article URL matches an existing article
- **THEN** the system SHALL detect the existing article by original URL
- **AND** it SHALL NOT insert a duplicate article

### Requirement: RSS-backed fetches report upstream source state
The article fetch pipeline SHALL update RSS source health state when feed requests succeed, fail, return empty results, or appear stale.

#### Scenario: RSS source fetch succeeds
- **WHEN** an RSS source fetch successfully reads and parses the feed
- **THEN** the system SHALL record the source's last successful fetch time
- **AND** it SHALL reset consecutive failure state for that feed

#### Scenario: RSS source fetch fails
- **WHEN** an RSS source fetch cannot request or parse the feed
- **THEN** the system SHALL record the failure for source health diagnostics
- **AND** it SHALL surface the source fetch as failed without marking unrelated RSS sources as failed
