## ADDED Requirements

### Requirement: Article publish time is normalized to Asia/Shanghai before persistence

The system SHALL normalize article publish times to Asia/Shanghai local time before writing them into `articles.publish_time`, and the persisted value SHALL be a naive datetime that represents Shanghai local time.

#### Scenario: Unix timestamp from provider is persisted as Shanghai local time
- **WHEN** a provider returns article publish time as a Unix timestamp
- **THEN** the system SHALL interpret that timestamp as an absolute instant
- **AND** it SHALL convert the instant to Asia/Shanghai local time before persistence
- **AND** the persisted `articles.publish_time` value SHALL not retain UTC clock time

#### Scenario: Timezone-aware ISO string is persisted as Shanghai local time
- **WHEN** a provider returns article publish time as an ISO datetime string with timezone information
- **THEN** the system SHALL convert that datetime to Asia/Shanghai local time before persistence
- **AND** it SHALL store the converted Shanghai local clock time as a naive datetime

#### Scenario: Naive page-parsed publish time remains local clock time
- **WHEN** article publish time is parsed from a WeChat article page as a naive datetime string without timezone information
- **THEN** the system SHALL treat that value as already representing local publication time
- **AND** it SHALL persist the same local clock time without an additional UTC conversion

### Requirement: Publish time backfill uses the same Shanghai-local normalization contract

The system SHALL apply the same Asia/Shanghai normalization contract when backfilling missing article publish times from provider metadata.

#### Scenario: Backfill writes provider publish time into missing article record
- **WHEN** the system backfills a missing `articles.publish_time` from provider article metadata
- **THEN** it SHALL normalize the provider value to Asia/Shanghai local time before persistence
- **AND** the backfilled value SHALL match the storage semantics used by newly inserted articles

### Requirement: Historical weread records can be corrected from UTC-naive persistence

The system SHALL provide a controlled way to correct existing `weread` article records that were previously persisted as UTC clock time in a naive `DateTime` field.

#### Scenario: Repair previously mis-persisted weread article time
- **WHEN** an existing article record is identified as originating from the affected `weread` persistence path
- **THEN** the system SHALL shift the stored publish time to the equivalent Asia/Shanghai local clock time
- **AND** it SHALL update the record in place without changing the article identity

#### Scenario: Repair scope avoids unrelated providers
- **WHEN** the system executes the historical repair path
- **THEN** it SHALL restrict correction to records that match the declared affected source criteria
- **AND** it SHALL NOT blindly shift all article records regardless of source

### Requirement: Downstream article time comparisons use the normalized Shanghai-local contract

The system SHALL ensure downstream comparisons that rely on `Article.publish_time`, including incremental fetch comparisons and market-summary article-window queries, operate on the normalized Shanghai-local storage contract.

#### Scenario: Market-summary article window matches post-close article after normalization
- **WHEN** a post-close article is published at Shanghai local time after the trade date close
- **THEN** the stored `Article.publish_time` SHALL fall into the expected market-summary article window for that trade date
- **AND** the article SHALL be eligible for inclusion without requiring an additional timezone correction at query time

#### Scenario: Incremental fetch compares normalized local publish times
- **WHEN** the system compares a provider article publish time against the latest stored article time during incremental fetch
- **THEN** both sides of the comparison SHALL use the same Shanghai-local time semantics
- **AND** the comparison SHALL NOT stop early because one side still reflects UTC clock time

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
## Requirements
### Requirement: 抓取流程中的等待调用使用抖动间隔

`FetcherService` SHALL 使用抖动等待方法替代固定的翻页间和文章间等待，实际等待 = base + random(0, jitter)。涉及的调用点包括 `_fetch_feed_summary`、`_fetch_incremental_summary` 和 `backfill_publish_time`。

#### Scenario: _fetch_feed_summary 翻页等待使用抖动
- **WHEN** `_fetch_feed_summary` 在第 2 页及之后的翻页前执行等待
- **THEN** 等待时间 SHALL 使用 `fetch_page_interval + random(0, fetch_page_jitter)`

#### Scenario: _fetch_feed_summary 文章间等待使用抖动
- **WHEN** `_fetch_feed_summary` 抓取新文章后执行等待
- **THEN** 等待时间 SHALL 使用 `fetch_article_interval + random(0, fetch_article_jitter)`

#### Scenario: _fetch_incremental_summary 翻页等待使用抖动
- **WHEN** `_fetch_incremental_summary` 在翻页前执行等待
- **THEN** 等待时间 SHALL 使用 `fetch_page_interval + random(0, fetch_page_jitter)`

#### Scenario: backfill_publish_time 翻页等待使用抖动
- **WHEN** `backfill_publish_time` 在翻页前执行等待
- **THEN** 等待时间 SHALL 使用 `fetch_page_interval + random(0, fetch_page_jitter)`

### Requirement: Batch progress uses effective trade day

`FetcherService.fetch_all()` SHALL track batch progress by effective A-share trade day rather than by calendar day. The effective fetch trade day SHALL be the latest A-share trade day for the current Shanghai-local time, with the trade-day boundary at 09:15.

#### Scenario: Weekend rerun keeps previous trade-day batch
- **WHEN** `fetch_all()` is invoked on a weekend
- **THEN** the system SHALL use the latest previous A-share trade day as the batch date
- **AND** subscriptions already marked `done` for that trade day SHALL be skipped

#### Scenario: Holiday rerun keeps previous trade-day batch
- **WHEN** `fetch_all()` is invoked on a non-weekend exchange holiday
- **THEN** the system SHALL use the latest previous A-share trade day as the batch date
- **AND** it SHALL NOT create a fresh batch only because the calendar date changed

#### Scenario: Trade day before 09:15 uses previous trade-day batch
- **WHEN** `fetch_all()` is invoked on an A-share trade day before 09:15 local time
- **THEN** the system SHALL use the previous A-share trade day as the batch date
- **AND** completed subscriptions from that previous trade-day batch SHALL remain skipped

#### Scenario: Trade day at or after 09:15 uses current trade-day batch
- **WHEN** `fetch_all()` is invoked on an A-share trade day at or after 09:15 local time
- **THEN** the system SHALL use the current A-share trade day as the batch date
- **AND** it SHALL create or resume batch progress for that trade day

### Requirement: Batch operations consistently use the effective trade day

All `fetch_all()` batch operations SHALL use the same effective trade-day value within one invocation, including batch creation, pending-feed lookup, done marking, cleanup cutoff calculation, and force reset.

#### Scenario: Successful feed is marked done for effective trade day
- **WHEN** a feed is successfully fetched during `fetch_all()`
- **THEN** the system SHALL mark that feed `done` for the effective trade-day batch
- **AND** it SHALL NOT mark a calendar-day batch for a different date

#### Scenario: Force resets effective trade-day batch
- **WHEN** `wchat fetch --all --force` is invoked
- **THEN** the system SHALL delete batch records for the effective trade day
- **AND** it SHALL create fresh `pending` records for active subscriptions under that same effective trade day

#### Scenario: Completion message identifies effective trade day
- **WHEN** all subscriptions for the effective trade-day batch are already `done`
- **THEN** the CLI SHALL report completion for that trade day
- **AND** the message SHALL NOT imply that the batch is tied to the current calendar day

### Requirement: Existing batch schema remains compatible

The system SHALL continue using the existing `fetch_batches.batch_date` column and `(mp_id, batch_date)` uniqueness constraint, while interpreting `batch_date` as the effective fetch trade date for new batch records.

#### Scenario: New records store effective trade date
- **WHEN** the system creates `fetch_batches` records after this change
- **THEN** each record's `batch_date` SHALL equal the effective fetch trade date
- **AND** the record SHALL remain unique by `mp_id` and `batch_date`

#### Scenario: Old batch rows are not migrated
- **WHEN** old `fetch_batches` rows exist from calendar-day behavior
- **THEN** the system SHALL NOT require a database migration before running `fetch_all()`
- **AND** normal retention cleanup SHALL eventually remove stale rows

<!-- delta from add-rss-auto-subscribe-and-docs -->
## ADDED Requirements

### Requirement: RSS imports resolve local Feed before article persistence
The article fetch pipeline SHALL resolve or create the owning local `Feed` for each RSS-imported article before inserting the article.

#### Scenario: RSS article belongs to existing feed
- **WHEN** an RSS item identifies a public account that already exists locally
- **THEN** the imported article SHALL use that existing feed as its owner
- **AND** no duplicate feed SHALL be created

#### Scenario: RSS article belongs to discovered feed
- **WHEN** an RSS item identifies a public account that does not exist locally
- **AND** auto-subscribe policy creates a local subscription
- **THEN** the imported article SHALL reference the newly created feed

### Requirement: RSS import handles unknown public-account identity according to policy
The article fetch pipeline SHALL handle RSS items whose public-account identity cannot be resolved without corrupting article ownership.

#### Scenario: Unknown identity with auto-subscribe disabled
- **WHEN** RSS import encounters an item with no matching local feed
- **AND** auto-subscribe is disabled
- **THEN** the system SHALL skip, fail, or stage the item according to the configured unknown-feed policy
- **AND** it SHALL NOT insert the article under an unrelated feed

#### Scenario: Unknown identity with placeholder creation allowed
- **WHEN** RSS import encounters an item with insufficient public-account identity
- **AND** placeholder creation is allowed by policy
- **THEN** the system SHALL create a traceable placeholder feed
- **AND** it SHALL preserve raw RSS metadata for later correction

### Requirement: RSS article source membership remains separate from canonical Feed ownership
The article fetch pipeline SHALL preserve RSS source/category membership independently from the canonical public-account feed owner.

#### Scenario: Same account appears in multiple RSS sources
- **WHEN** RSS import processes articles from the same public account across multiple RSS sources
- **THEN** the articles SHALL share the same canonical feed owner when matched
- **AND** source/category memberships SHALL be preserved separately

#### Scenario: Same article appears in multiple RSS sources
- **WHEN** the same article URL appears in multiple RSS sources
- **THEN** the system SHALL keep one canonical article record
- **AND** it SHALL record each source membership without duplicating the article
