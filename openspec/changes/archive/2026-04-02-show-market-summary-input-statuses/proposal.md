## Why

`market-summary` 在进入 AI 总结前，虽然已经展示了阶段性摘要和部分状态信息，但还没有以统一、逐项的方式明确告诉用户“AI 即将消费哪些输入数据、每类数据是否成功、以及拿到了多少”。这让用户在排查总结质量、判断数据缺口和理解降级执行时，仍然需要从分散输出中自行拼接上下文。

现在需要把这部分可见性收口成稳定的 CLI 行为，让用户在 AI 开始前直接看到一份简洁的输入数据清单。

## What Changes

- 调整 `wchat ai market-summary` 在 AI 开始前的预检输出，展示统一的输入数据清单。
- 将预检输出改为逐项列出每类输入数据，而不是只按成功、失败、无数据做分组汇总。
- 对市场数据和新闻数据统一展示三类信息：数据类型、状态、数量或计数摘要。
- 保持现有数据采集逻辑和 AI prompt 结构不变，本次只收口 CLI 可见性与对应测试。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整市场总结在 AI 开始前的 CLI 展示语义，要求输出逐项输入数据清单，并为每类输入展示状态和数量摘要。

## Impact

- **Affected code**:
  - `src/cli/ai.py`
  - 可能少量影响 `src/cli/utils.py`
- **Affected tests**:
  - `tests/test_market_summary_cli_flow.py`
- **Affected behaviors**:
  - `wchat ai market-summary`
  - `wchat ai market-summary --offline`
  - `wchat ai market-summary --force`
