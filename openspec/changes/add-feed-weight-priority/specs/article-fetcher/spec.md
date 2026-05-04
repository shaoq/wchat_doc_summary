## MODIFIED Requirements

### Requirement: Downstream article time comparisons use the normalized Shanghai-local contract

The system SHALL ensure downstream comparisons that rely on `Article.publish_time`, including incremental fetch comparisons and market-summary article-window queries, operate on the normalized Shanghai-local storage contract. Batch fetch ordering SHALL respect feed weight priority.

#### Scenario: Market-summary article window matches post-close article after normalization
- **WHEN** a post-close article is published at Shanghai local time after the trade date close
- **THEN** the stored `Article.publish_time` SHALL fall into the expected market-summary article window for that trade date
- **AND** the article SHALL be eligible for inclusion without requiring an additional timezone correction at query time

#### Scenario: Incremental fetch compares normalized local publish times
- **WHEN** the system compares a provider article publish time against the latest stored article time during incremental fetch
- **THEN** both sides of the comparison SHALL use the same Shanghai-local time semantics
- **AND** the comparison SHALL NOT stop early because one side still reflects UTC clock time

## ADDED Requirements

### Requirement: Batch fetch orders by feed weight
`FetcherService.fetch_all()` SHALL fetch feeds in the order returned by `list_subscriptions_for_fetch()`, which prioritizes high-weight feeds.

#### Scenario: fetch_all uses weight-based ordering
- **WHEN** `fetch_all()` is invoked
- **THEN** it SHALL call `list_subscriptions_for_fetch()` instead of `list_subscriptions()`
- **AND** feeds SHALL be processed in weight-descending order
