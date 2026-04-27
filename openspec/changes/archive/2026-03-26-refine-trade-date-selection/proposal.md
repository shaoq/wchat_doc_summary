# Proposal: 优化交易日选择逻辑

## Why

当前 `market-summary` 命令在交易日当天开市前(09:00 前)执行时,会返回空数据:
因为时间窗口从 09:00 开始,还没到时间点就查不到任何数据.

用户期望的是获取**上一个已结束的交易日**的总结.

## What Changes
1. 修改 `get_latest_trade_date()` 方法, 添加时间判断逻辑:
   - 交易日 09:00 前 → 返回上一个交易日
   - 交易日 09:00 后 → 返回今天
2. 保持非交易日的行为不变

## Capabilities
### New Capabilities
- `smart-trade-date`: 智能交易日选择逻辑

### Modified Capabilities
无

## Impact
- **受影响代码**:
  - `src/services/market_analyzer.py`: `get_latest_trade_date()` 方法
- **受影响命令**:
  - `wchat ai market-summary`
