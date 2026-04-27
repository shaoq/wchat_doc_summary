## Why

当使用 `wchat ai market-summary --force` 重复执行时，会触发数据库唯一约束错误：
```
UNIQUE constraint failed: market_summaries.trade_date
```

`--force` 参数的语义是"强制重新生成（覆盖已有）"，但当前实现只跳过了检查，没有实现覆盖逻辑，导致重复执行失败。

## What Changes

- 修改 `MarketAnalyzer.save_summary()` 方法，实现 upsert 模式
- 当记录已存在时更新内容，不存在时插入新记录
- 保持 `--force` 参数的语义一致性

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

- `market-summary`: 修改 `save_summary()` 方法的行为，支持覆盖已有记录

## Impact

| 文件 | 影响 |
|------|------|
| `src/services/market_analyzer.py` | 修改 `save_summary()` 方法，添加 upsert 逻辑 |
| `src/cli.py` | 无需修改（已正确检查 `--force`） |
