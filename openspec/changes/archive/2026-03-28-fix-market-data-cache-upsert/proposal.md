## Why

`wchat ai market-summary --force` 在当前交易日重复执行时，市场数据缓存层会再次写入相同 `trade_date` 的记录，触发 `market_indices.trade_date` 等唯一约束错误。`--force` 的语义本应是跳过读取缓存并用最新结果覆盖缓存，但当前实现没有兑现这一点，导致命令在已有缓存场景下不稳定。

## What Changes

- 修正市场数据缓存写入逻辑，使指数、成交额、涨跌统计、板块、涨停股在相同交易日重复保存时执行覆盖更新而不是重复插入。
- 明确 `market-summary --force` 在命中已有市场数据缓存时的行为：跳过读取旧缓存、重新抓取在线数据，并将结果安全写回同一交易日缓存。
- 为市场数据缓存补充重复保存和强制刷新场景的测试，确保不再出现 SQLite 唯一约束错误。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-data-cache`: force refresh 和重复保存同一交易日数据时，缓存写入必须表现为 upsert，不能因唯一约束失败。
- `market-summary`: `--force` 在已有市场数据缓存时必须能够成功完成并覆盖缓存，不得因缓存层数据库错误中断。

## Impact

- `src/services/market_data_cache_service.py`
- `src/services/market_analyzer.py`
- `tests/test_market_data_cache_service.py`
- `tests/test_service_integration.py`
- 可能补充 `market-summary` 强制刷新相关 CLI / 集成测试
