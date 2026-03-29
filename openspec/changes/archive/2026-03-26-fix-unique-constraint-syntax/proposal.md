## Why

SQLAlchemy 模型定义中使用了不正确的 `UniqueConstraint` 参数格式，导致 `TypeError:。

错误信息： `Additional arguments should be named <dialectname>_<argument>, got 'UniqueConstraint'`

这个错误发生在 `MarketSector` 和 `LimitUpStock` 模型中，当 `__table_args__` 元组只有一个 `UniqueConstraint` 元素时,SQLAlchemy 将其解释为命名参数而不是约束对象。

## What Changes
修复 `MarketSector` 和 `LimitUpStock` 模型的 `__table_args__ 定义,使其兼容 SQLAlchemy 2.0:
- 将 `UniqueConstraint` 放在列表末尾
- 在元组末尾添加字典指定表选项 (如 `sqlite_autoincrement`)
- 硆保唯一约束逻辑不变

## Capabilities
### New Capabilities
(none)

### Modified Capabilities
- `market-sectors-storage`: 修复 MarketSector 模型的唯一约束语法
- `limit-up-stocks-storage`: 修复 LimitUpStock 模型的唯一约束语法

## Impact
- `src/models/schema.py`: 修复 `MarketSector` 和 `LimitUpStock` 模型的 `__table_args__` 定义
