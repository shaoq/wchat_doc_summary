## Why

`market-summary` 主链路已经完成大部分重构，但当前 CLI 编排仍有几个执行层缺口：`--date` 与 `--force` 没有真正传入市场数据收集链路，`--offline` 在无本地缓存时行为不够明确，且这些关键分支缺少流程级测试保护。如果不单独收口，用户可见行为会继续偏离提案预期。

## What Changes

- 修复 `market-summary` CLI 对 `trade_date` 和 `force` 参数的透传，确保市场数据获取与用户指定参数一致。
- 明确 `--offline` 在“无本地市场数据”场景下的 CLI 行为，并使其与当前规格保持一致。
- 为 `market-summary` CLI 增加关键流程测试，覆盖 `--date`、`--force`、`--offline` 和 `--list` 的真实编排行为。
- 补充针对市场数据收集调用参数的一致性测试，防止后续回归。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 修正 CLI 参数透传、离线失败行为和关键流程测试覆盖，使市场总结执行行为与规格一致。

## Impact

- **Affected code**:
  - `src/cli/ai.py`
  - 可能少量影响 `src/services/market_analyzer.py`
- **Affected tests**:
  - 需要新增或扩展 `market-summary` CLI 流程测试
  - 可能补充 `MarketAnalyzer.collect_market_data()` 调用参数测试
- **Affected behaviors**:
  - `wchat ai market-summary --date`
  - `wchat ai market-summary --force`
  - `wchat ai market-summary --offline`
  - `wchat ai market-summary --list`
