## Why

`wchat ai market-summary --list` 只是读取本地已保存的市场总结，但当前实现会在进入列表分支前初始化 `AIProcessor`，导致没有配置 LLM API Key 时连历史列表都无法查看。一个纯本地只读操作不应被远端 AI 配置阻塞。

## What Changes

- 让 `market-summary --list` 不再依赖 `AIProcessor` 初始化。
- 收紧 `market-summary` 各分支的依赖初始化顺序，只在真正需要 AI 生成时才初始化 LLM 相关对象。
- 补充 `--list` 在未配置 LLM 环境下的回归测试。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整历史总结列表分支的依赖初始化行为，确保列表查看不受 LLM 配置影响。

## Impact

- **Affected code**:
  - `src/cli/ai.py`
  - 可能少量影响 `src/services/ai_processor.py` 的初始化调用时机
- **Affected tests**:
  - `tests/test_market_summary_cli_flow.py`
  - 需要新增无 LLM 配置下的 `--list` 测试
- **Affected behaviors**:
  - `wchat ai market-summary --list`
