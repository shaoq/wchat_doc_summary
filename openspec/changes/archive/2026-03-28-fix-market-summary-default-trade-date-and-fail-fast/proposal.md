## Why

`market-summary` 当前已经覆盖市场数据、文章和 CLS 资料的聚合，但默认执行路径仍有两个直接影响结果可信度的缺口：非交易日执行时不一定回退到最近交易日，以及市场数据不可用时 CLI 仍可能继续生成总结。只要这两个问题存在，周末执行和失败场景下的输出就会失去解释性。

## What Changes

- 修正 `market-summary` 默认 `trade_date` 的选择逻辑，确保非交易日执行时回退到最近交易日。
- 修正交易日开盘前默认执行时的回退逻辑，确保使用上一个交易日。
- 明确 `market-summary` 在市场数据不可用时的停止语义，不再基于空行情继续生成总结。
- 补充针对周末、开盘前、历史无数据和在线失败场景的 CLI / service 回归测试。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整默认交易日选择与市场数据失败处理行为，确保生成链路在错误场景下停止而不是静默降级。

## Impact

- **Affected code**:
  - `src/services/market_analyzer.py`
  - `src/cli/ai.py`
- **Affected tests**:
  - `tests/test_trade_day_boundaries.py`
  - `tests/test_historical_market_data.py`
  - `tests/test_market_summary_cli_flow.py`
- **Affected behaviors**:
  - `wchat ai market-summary`
  - 周末和开盘前默认 `trade_date`
  - 市场数据不可用时的 CLI 停止逻辑
