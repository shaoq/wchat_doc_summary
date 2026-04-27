## What

修复 `MarketSector` 模型中 SQLAlchemy 2.0 的 `__table_args__` 元组只有 `UniqueConstraint` 时，会导致 SQLAlchemy 报错：
`Additional arguments should be named <dialectname>_<argument>, got 'UniqueConstraint'`。

## What Changes

修改 `MarketSector` 和 `LimitUpStock` 模型的 `__table_args__` 定义，将 `UniqueConstraint` 元组改为字典格式。

## Capabilities
### New Capabilities
- `market-sectors-storage`: 新增 Market板块数据缓存模型
- `limit-up-stocks-storage`: 新增涨停股数据缓存模型
### Modified Capabilities
- `market-sectors-storage`: 修复唯一约束语法
- `limit-up-stocks-storage`: 修复唯一约束语法

## Impact
- `src/models/schema.py`: 修改 `__table_args__` 定义
- 数据库表 `market_sectors` 和 `limit_up_stocks` 的唯一约束
