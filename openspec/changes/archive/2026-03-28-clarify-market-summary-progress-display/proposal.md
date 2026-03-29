## Why

`market-summary` 现在虽然已经有三阶段进度提示，但执行输出仍然偏散：阶段标题不持久、数据来源语义不明确、AI 生成与保存结果没有形成闭环。用户在长流程中很难快速判断“当前跑到哪一步、这轮用了什么数据、结果是否已经真正落盘”。

## What Changes

- 将 `market-summary` 的执行输出收紧为更稳定的阶段块展示，而不是只保留零散的 spinner 文案和摘要行。
- 明确显示执行上下文，包括交易日、执行模式以及市场数据策略或数据来源语义。
- 收紧三个阶段的输出结构：每个阶段都包含标题、状态结论和关键细节，且第 3 阶段显式覆盖“生成并保存总结”的完整闭环。
- 为新的进度展示结构补充 CLI 流程测试，锁住阶段顺序、来源标识和保存结果展示。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-summary`: 命令执行过程的进度展示、数据来源提示和完成态输出需要更清楚、更稳定，便于用户理解当前阶段和最终结果。

## Impact

- `src/cli/ai.py`
- `src/cli/utils.py`
- `tests/test_market_summary_cli_flow.py`
- `openspec/specs/market-summary/spec.md`
