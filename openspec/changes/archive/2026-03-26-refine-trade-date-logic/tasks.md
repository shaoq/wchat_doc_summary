# Tasks: 优化交易日判断逻辑

## 1. 修改 get_latest_trade_date 方法
- [x] 1.1 在 `src/services/market_analyzer.py` 中修改 `get_latest_trade_date()` 方法
  - 添加当前时间判断逻辑: 如果当前时间 < 09:00 且今天是交易日. 返回上一个交易日
  - 否则保持现有行为

## 2. 验证修改
- [x] 2.1 手动验证: 运行 `wchat ai market-summary` 命令
  - 交易日 07:00 执行 → 返回上一个交易日 ✓
  - 交易日 10:00 执行 → 返回今天 ✓
  - 非交易日任意时间执行 → 返回最近交易日 ✓
