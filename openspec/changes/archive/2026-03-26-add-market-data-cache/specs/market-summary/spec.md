## ADDED Requirements

### Requirement: Use cache service for market data

The `market-summary` command SHALL use `MarketDataCacheService` to get market data instead of directly calling `FinanceClient`.

#### Scenario: Market summary uses cache
- **WHEN** user runs `wchat market-summary --date 2026-03-25`
- **THEN** system calls `MarketDataCacheService.get_market_data(2026-03-25)`
- **AND** cache service handles cache lookup and API calls

### Requirement: Support force refresh in market-summary CLI

The `market-summary` command SHALL support `--force` flag to bypass cache.

#### Scenario: Force refresh market summary
- **WHEN** user runs `wchat market-summary --force`
- **THEN** system ignores cached data
- **AND** fetches fresh data from APIs
- **AND** updates cache if conditions are met
