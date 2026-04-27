## REMOVED Requirements

### Requirement: Volume and rise-fall statistics share one market snapshot strategy
**Reason**: 成交额与涨跌统计的最佳免费主源不同，继续强制共享同一份底层快照会降低整体可用性与正确性。
**Migration**: 成交额改为交易所官方盘后统计主源，涨跌统计改为 `pytdx` 主源，二者仅需共享同一交易日语义与统一 contract。

## ADDED Requirements

### Requirement: Volume data uses official exchange turnover sources

The system SHALL fetch Shanghai and Shenzhen stock turnover from official exchange post-close sources before attempting any legacy fallback strategy.

#### Scenario: Official exchange turnover succeeds
- **WHEN** the system generates market-summary market data for a completed trade date
- **THEN** it SHALL fetch Shanghai stock turnover from the Shanghai exchange official source
- **AND** it SHALL fetch Shenzhen stock turnover from the Shenzhen exchange official source
- **AND** it SHALL normalize the result into `sh_volume`, `sz_volume`, and `total_volume`

#### Scenario: Official exchange turnover partially fails
- **WHEN** one official exchange turnover source is unavailable or malformed
- **THEN** the system SHALL mark turnover quality as degraded for that trade date
- **AND** it SHALL attempt the declared legacy fallback strategy for the missing turnover data
- **AND** if fallback also fails, it SHALL return the normalized zero-value turnover contract

### Requirement: Rise-fall statistics use a pytdx A-share quote strategy

The system SHALL compute rise-fall statistics from `pytdx` quotes over an explicitly filtered A-share universe before attempting any legacy fallback strategy.

#### Scenario: pytdx quote aggregation succeeds
- **WHEN** the system can fetch `pytdx` quotes for the maintained A-share universe
- **THEN** it SHALL compute `up_count`, `down_count`, and `flat_count` from `price` and `last_close`
- **AND** the universe SHALL only include supported A-share prefixes

#### Scenario: pytdx quote aggregation fails
- **WHEN** the `pytdx` quote strategy is unavailable, incomplete, or malformed
- **THEN** the system SHALL attempt the declared legacy fallback strategy for rise-fall statistics
- **AND** if fallback also fails, it SHALL return the normalized zero-value statistics contract

### Requirement: Volume and rise-fall statistics share trade-date semantics

The system SHALL ensure turnover and rise-fall statistics correspond to the same trade date even when they are produced by different primary sources.

#### Scenario: Mixed primary sources succeed
- **WHEN** official turnover and `pytdx` rise-fall statistics both succeed for the same trade date
- **THEN** the system SHALL expose both results in one normalized market data payload
- **AND** the source strategy metadata SHALL make clear that the two width metrics came from different primary sources
