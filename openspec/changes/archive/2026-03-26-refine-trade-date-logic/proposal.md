# Proposal: 优化交易日判断逻辑

## Why

当前 `market-summary` 命令在**交易日当天开市前**执行时，会返回空数据（0 条电报、0 篇文章）。这是因为系统默认使用"今天"作为交易日。但时间窗口从 09:00 开始，如果当前时间还没到 09:00，就查不到任何数据。

**场景示例**:
- 今天是 2026-03-26（周四，交易日）
- 用户在 07:47 执行 `wchat ai market-summary`
- 系统判断 trade_date = 2026-03-26
- 电报窗口: 2026-03-26 09:00 ~ 2026-03-27 09:00
- 当前时间 07:47 还没到窗口起点 → 查到 0 条数据

用户期望获取的是**上一个已结束的交易日**（2026-03-25）的总结。

## What Changes

1. **修改 `get_latest_trade_date()` 逻辑**: 在交易日当天，如果当前时间还没到 09:00（开盘时间），则自动返回**上一个交易日**
2. **添加新方法 `get_effective_trade_date()`**: 封装智能交易日判断逻辑，考虑当前时间是否已开盘

## Capabilities

### New Capabilities

- `trading-time-window`: 交易日时间窗口判断逻辑

### Modified Capabilities

无（此次变更仅修改现有方法的实现逻辑，不改变 API 契约）

## Impact

- **受影响代码**:
  - `src/services/market_analyzer.py`: 修改 `get_latest_trade_date()` 或添加新方法
- **受影响命令**:
  - `wchat ai market-summary`: 执行结果变化（在开市前自动获取上一交易日数据）
