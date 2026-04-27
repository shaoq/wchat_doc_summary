## 1. Data Models

- [x] 1.1 Add `MarketIndex` model to `src/models/schema.py` for indices data
- [x] 1.2 Add `MarketVolume` model to `src/models/schema.py` for volume data
- [x] 1.3 Add `MarketStatistics` model to `src/models/schema.py` for statistics data
- [x] 1.4 Add `MarketSector` model to `src/models/schema.py` for sector data
- [x] 1.5 Add `LimitUpStock` model to `src/models/schema.py` for limit-up stocks

## 2. Cache Service

- [x] 2.1 Create `src/services/market_data_cache_service.py` with `MarketDataCacheService` class
- [x] 2.2 Implement `should_cache(trade_date)` method for cache decision logic
- [x] 2.3 Implement `get_cached(trade_date)` method to query all cached data
- [x] 2.4 Implement `save_market_data(trade_date, data)` method to store all data types
- [x] 2.5 Implement `get_market_data(trade_date, force_refresh=False)` main method
- [x] 2.6 Implement `delete_cache(trade_date)` method for cache invalidation

## 3. Integration

- [x] 3.1 Modify `MarketAnalyzer.collect_market_data()` to use `MarketDataCacheService`
- [x] 3.2 Add `--refresh-cache` flag to `market-summary` CLI command
- [x] 3.3 Pass `force_refresh` parameter from CLI to cache service

## 4. Testing

- [ ] 4.1 Write unit tests for `MarketDataCacheService.should_cache()`
- [ ] 4.2 Write unit tests for `MarketDataCacheService.get_cached()`
- [ ] 4.3 Write unit tests for `MarketDataCacheService.save_market_data()`
- [ ] 4.4 Write integration tests for cache flow with `MarketAnalyzer`
- [ ] 4.5 Write tests for `--refresh-cache` flag behavior

## 5. Documentation

- [ ] 5.1 Update CLI help text for `--refresh-cache` flag
- [ ] 5.2 Add docstrings to all new methods and classes
