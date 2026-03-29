## Why

东方财富 API（push2.eastmoney.com）在非交易时间持续返回空响应，导致板块数据和涨停股数据无法获取。即使使用 curl 绕过代理也无法解决此问题。需要切换到更稳定的 akshare 数据源来确保数据的可靠性。

## What Changes

- **板块数据获取方式切换**: 从 `SectorClient`（东方财富 curl）切换到 akshare `stock_sector_spot`（新浪数据源）
- **涨停股数据获取方式切换**: 从 `EastMoneyCurlClient`（东方财富 curl）切换到 akshare `stock_zt_pool_em`
- **数据模型适配**: 调整 `SectorData` 模型以适配新的数据结构
- **降级逻辑简化**: 移除失效的东方财富 curl 降级路径，简化为直接使用 akshare

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

- `sector-data`: 修改板块数据获取方式，从东方财富 API 切换到 akshare stock_sector_spot（新浪数据源），数据字段保持兼容
- `limit-up-data`: 修改涨停股数据获取方式，从东方财富 API 切换到 akshare stock_zt_pool_em，增加连板数等扩展字段

## Impact

- **受影响文件**:
  - `src/api/finance.py` - 修改 `get_sector_data()` 和 `get_limit_up_stocks()` 方法
  - `src/api/sector.py` - 可能废弃或重构（取决于是否保留作为备用）
  - `src/models/schema.py` - `SectorData` 模型可能需要调整
- **API 变更**: 内部实现变更，外部接口保持兼容
- **依赖变更**: 无新增依赖，akshare 已在项目中
