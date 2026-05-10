## ADDED Requirements

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
