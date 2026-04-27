## Why

当前 `market-summary` 已经具备文章、财联社电报和财联社看盘三类资料的聚合能力，但默认交易日回退和资料时间窗口语义仍不稳定：非交易日执行时不一定正确回退到最近交易日，而且三类资料的窗口划分还没有和它们各自的职责明确对齐。继续在这种模糊语义上迭代，会让周末、节假日前后和开盘前场景下的总结结果变得不可解释。

## What Changes

- 明确 `market-summary` 在非交易日执行时，默认使用最近交易日作为 `trade_date`。
- 为 `market-summary` 定义按资料类型区分的窗口规则，而不是用一套统一窗口覆盖所有来源。
- 将财联社看盘数据限定为交易日盘中窗口，用于还原当日走势和轮动。
- 将财联社电报窗口扩展为“交易日盘中到下一个交易日开盘前”，覆盖盘中重要消息、盘后消息、周末消息和开盘前消息。
- 保持文章窗口为“交易日收盘后到下一个交易日开盘前”，聚焦复盘与开盘前观点。
- 让 CLI 展示的时间窗口与各资料类型的实际查询窗口一致，并补充相应测试。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整默认交易日回退规则，以及文章、财联社电报、财联社看盘三类资料的时间窗口语义。

## Impact

- **Affected code**:
  - `src/services/market_analyzer.py`
  - `src/services/cls_watch_service.py`
  - `src/services/cls_telegraph_service.py`
  - `src/cli/ai.py`
- **Affected tests**:
  - `tests/test_market_analyzer.py`
  - `tests/test_market_summary_cli_flow.py`
  - 需要新增周末与开盘前场景的时间窗口测试
- **Affected behaviors**:
  - `wchat ai market-summary`
  - 周末执行时默认 `trade_date`
  - 文章 / 财联社电报 / 财联社看盘的资料收集窗口
