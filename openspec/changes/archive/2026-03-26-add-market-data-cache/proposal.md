## Why

当前系统每次执行 `market-summary` 都会调用外部 API 获取市场数据（指数、成交额、涨跌统计、板块、涨停股），即使对于已收盘的历史交易日也是如此。这导致：
1. **重复请求**：同一交易日的数据被多次获取，浪费 API 配额
2. **封禁风险**：频繁请求可能触发反爬虫机制（如新浪 IP 封禁）
3. **性能开销**：每次都要等待网络请求，即使数据已确定不变

收盘后的市场数据是静态的，应当缓存到本地数据库，避免重复获取。

## What Changes

- 新增市场数据缓存层，在收盘后（15:00）自动存储获取到的数据
- 支持按交易日查询缓存数据，优先返回本地缓存
- 新增 5 张数据表分别存储：指数、成交额、涨跌统计、板块、涨停股
- 新增 `MarketDataCacheService` 服务层封装缓存逻辑
- CLI 支持 `--force` 参数强制刷新缓存

## Capabilities

### New Capabilities

- `market-data-cache`: 市场数据缓存能力 - 提供指数、成交额、涨跌统计、板块、涨停股的本地缓存存储和查询功能

### Modified Capabilities

- `market-summary`: 修改数据获取逻辑，从直接调用 API 改为优先使用缓存服务

## Impact

- **新增文件**:
  - `src/services/market_data_cache_service.py` - 缓存服务
  - `src/models/market_data.py` - 新数据模型（或扩展 schema.py）

- **修改文件**:
  - `src/models/schema.py` - 新增 5 张表的 ORM 模型
  - `src/services/market_analyzer.py` - 改用缓存服务获取数据
  - `src/cli.py` - 支持 `--force` 参数

- **数据库**:
  - 新增 5 张表：`market_indices`, `market_volume`, `market_statistics`, `market_sectors`, `limit_up_stocks`

- **API 调用**:
  - 减少 API 请求频率，降低被封禁风险
