## MODIFIED Requirements

### Requirement: Rise-fall statistics use a pytdx A-share quote strategy

The system SHALL compute rise-fall statistics by aggregating the local `daily_kline` table (populated by the TickFlow post-close pipeline) before attempting any legacy fallback strategy.

#### Scenario: Daily-K aggregation succeeds

- **WHEN** the post-close pipeline has populated `daily_kline` for the requested trade date
- **THEN** it SHALL compute `up_count`, `down_count`, and `flat_count` from `change_pct`
- **AND** the universe SHALL only include supported A-share prefixes

#### Scenario: Daily-K aggregation unavailable

- **WHEN** `daily_kline` lacks data for the requested trade date (pipeline not run or failed)
- **THEN** it SHALL attempt the declared legacy fallback strategy (pytdx) for rise-fall statistics
- **AND** if fallback also fails, it SHALL return the normalized zero-value statistics contract
