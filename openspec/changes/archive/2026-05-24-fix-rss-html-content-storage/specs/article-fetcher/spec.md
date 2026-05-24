## MODIFIED Requirements

### Requirement: RSS-backed article import is cache-first
The article fetch pipeline SHALL prefer feed-provided content for RSS-backed articles and avoid direct WeChat article-page fetching when the configured RSS content mode does not allow it. RSS-backed article body HTML SHALL be persisted in `Article.content`, not in `Article.summary`.

#### Scenario: Feed item includes HTML content
- **WHEN** an RSS-backed provider article includes HTML content
- **THEN** the system SHALL import that content without requesting the original article page
- **AND** the article SHALL still be deduplicated and persisted through the normal article storage path
- **AND** the feed-provided HTML body SHALL be stored in `Article.content`
- **AND** the same HTML body SHALL NOT be stored in `Article.summary`

#### Scenario: Feed HTML cannot be parsed as a full WeChat page
- **WHEN** an RSS-backed provider article provides an HTML body fragment
- **AND** the page parser does not extract a non-empty content field from that fragment
- **THEN** the system SHALL persist the original feed HTML fragment in `Article.content`
- **AND** it SHALL NOT discard the fragment only because full-page parsing failed

#### Scenario: Feed-only mode with missing content
- **WHEN** `rss_content_mode` is `feed_only` and an RSS-backed provider article lacks full content
- **THEN** the system SHALL NOT request the original article page
- **AND** it SHALL persist the available feed summary as `Article.summary` only when it is a textual summary rather than an HTML body
- **AND** it SHALL mark article content as unavailable without failing the whole subscription fetch when no body content is available

#### Scenario: Prefer-feed mode with missing content
- **WHEN** `rss_content_mode` is `prefer_feed` and an RSS-backed provider article lacks usable content
- **THEN** the system MAY request the original article page to fill missing content
- **AND** that direct request SHALL remain subject to existing fetch throttling and error handling

### Requirement: Historical RSS body HTML can be repaired
The system SHALL provide a controlled repair path for RSS-backed articles whose body HTML was previously stored in `Article.summary` while `Article.content` was empty.

#### Scenario: Repair affected RSS article
- **WHEN** an article has `provider='rss'`
- **AND** `Article.content` is empty
- **AND** `Article.summary` clearly contains HTML body content
- **THEN** the repair path SHALL copy that HTML into `Article.content`
- **AND** it SHALL clear or null out `Article.summary` unless a plain text summary can be safely derived

#### Scenario: Repair avoids non-RSS articles
- **WHEN** an article is not RSS-backed
- **THEN** the repair path SHALL NOT move `Article.summary` into `Article.content`

#### Scenario: Repair reports affected counts
- **WHEN** the repair path runs
- **THEN** it SHALL report how many rows matched the affected pattern
- **AND** it SHALL report how many rows were updated
