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

