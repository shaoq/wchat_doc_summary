## 1. Cache Upsert Semantics

- [x] 1.1 Refactor `MarketDataCacheService.save_market_data()` to upsert `MarketIndex`, `MarketVolume`, and `MarketStatistics` by `trade_date`
- [x] 1.2 Refactor `MarketDataCacheService.save_market_data()` to upsert `MarketSector` by `trade_date + sector_code`
- [x] 1.3 Refactor `MarketDataCacheService.save_market_data()` to upsert `LimitUpStock` by `trade_date + stock_code`

## 2. Force Refresh Flow

- [x] 2.1 Verify `MarketAnalyzer.collect_market_data(force=True)` preserves the existing “skip cache read, fetch fresh data” flow while relying on cache upsert for writes
- [x] 2.2 Ensure `wchat ai market-summary --force` no longer surfaces database UNIQUE constraint errors when same-trade-date market cache already exists

## 3. Regression Coverage

- [x] 3.1 Add unit or integration coverage for saving the same `trade_date` market data twice without duplicate-row errors
- [x] 3.2 Add assertions that repeated saves overwrite cached values for existing uniqueness keys instead of inserting duplicates
- [x] 3.3 Run targeted market data cache and market-summary related tests to verify the regression is closed
