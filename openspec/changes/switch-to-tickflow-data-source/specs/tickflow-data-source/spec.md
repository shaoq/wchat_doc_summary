## ADDED Requirements

### Requirement: TickFlow client SHALL use the free-api server without a paid key

The system SHALL initialize the TickFlow client via `TickFlow.free()` against the free-api server, which provides historical daily-K, index daily-K, and Shenwan industry universes but no real-time quotes.

#### Scenario: Free client initialized

- **WHEN** the market data provider is TickFlow and no paid key is configured
- **THEN** the client SHALL initialize `TickFlow.free()` against `free-api.tickflow.org`
- **AND** it SHALL NOT attempt real-time quote endpoints

### Requirement: TickFlow provider SHALL rate-limit batch daily-K at 60 rpm

The system SHALL enforce a process-wide shared timeline limiting batch daily-K requests to the free tier's 60 requests/minute (up to 100 symbols per request).

#### Scenario: Concurrent batches respect 60 rpm

- **WHEN** multiple batch daily-K requests are issued concurrently
- **THEN** the aggregate request rate SHALL NOT exceed 60 requests/minute
- **AND** each request SHALL carry up to 100 symbols

### Requirement: A post-close daily-K pipeline SHALL batch-fetch the full market

Because the free tier provides no full-market real-time snapshot, the system SHALL provide a post-close pipeline that batch-fetches full-market daily-K into a local `daily_kline` table.

#### Scenario: Incremental post-close fetch

- **WHEN** the post-close pipeline runs after a trade day
- **THEN** it SHALL fetch the latest trade day's daily-K for all symbols via `klines.batch` in chunks of 100
- **AND** it SHALL upsert rows into `daily_kline` keyed by `(symbol, trade_date)`

#### Scenario: First-time historical backfill

- **WHEN** `daily_kline` is empty
- **THEN** the pipeline SHALL fetch historical daily-K (e.g. 1 year) for all symbols
- **AND** it SHALL persist all rows before enabling aggregation

### Requirement: Aggregate metrics SHALL be computed locally from daily-K

Because the free tier lacks real-time snapshots, the provider SHALL compute volume, rise-fall statistics, limit-up pool, and full-market snapshot by aggregating the local `daily_kline` table.

#### Scenario: Rise-fall statistics computed locally

- **WHEN** statistics are requested
- **THEN** the provider SHALL aggregate `daily_kline.change_pct` to compute up / down / flat counts
- **AND** it SHALL NOT call any real-time quote endpoint

### Requirement: Sectors SHALL use Shenwan industry taxonomy aggregated from daily-K

The provider SHALL derive sector rows from Shenwan level-1 (SW1) industry universes by aggregating constituent daily-K `change_pct`, replacing the prior concept taxonomy (the TickFlow free tier provides industries, not concepts).

#### Scenario: Industry change computed from constituents

- **WHEN** sectors are requested
- **THEN** the provider SHALL load SW1 industry membership
- **AND** it SHALL aggregate constituent `change_pct` by industry mean
- **AND** it SHALL return industry rows aligned to the decimal dict contract

### Requirement: TickFlow values SHALL align to the internal decimal contract

TickFlow-returned percentage values SHALL be normalized to the internal decimal scale (e.g. `0.0522` for +5.22%) before entering the dict contract, to avoid the double-scaling pitfall in `_normalize_pct`.

#### Scenario: Percentage normalized once

- **WHEN** TickFlow returns a change value in percent or fractional form
- **THEN** the provider SHALL convert it to the internal decimal scale exactly once
- **AND** a unit test SHALL assert the final dict value is not scaled again by `_normalize_pct`

### Requirement: TickFlow SHALL auto-sync daily_kline before summary when stale

In tickflow/mixed mode, `get_all_market_data` SHALL ensure `daily_kline` has the latest trade day's data before aggregating; if stale or empty, it SHALL auto-trigger an incremental sync (latest day) so that pure-TickFlow `market-summary` does not analyze against missing/stale data.

#### Scenario: daily_kline is fresh

- **WHEN** `get_all_market_data` runs in tickflow/mixed mode
- **AND** `daily_kline.latest_date` is on or after the latest trade day
- **THEN** it SHALL skip the sync and aggregate directly

#### Scenario: daily_kline is stale or empty

- **WHEN** `daily_kline.latest_date` is before the latest trade day (or the table is empty)
- **THEN** it SHALL auto-trigger `sync(count=1)` before aggregating
- **AND** subsequent aggregation SHALL use the freshly-synced data
