## Why

`market-summary` 目前已经会输出分阶段执行进展，但实际终端展示仍然比较乱：阶段标题、结果摘要、来源统计、时间窗口和空行是分散拼接的，成功与失败路径的呈现方式也不一致。命令一旦执行较久，用户很难快速判断当前卡在哪个阶段、哪些资料为空、以及本次运行是否已经正常结束。

## What Changes

- 重新定义 `market-summary` 的 CLI 执行进展展示，改为结构稳定、顺序固定的阶段输出。
- 收敛阶段 1 的行情结果展示，让数据来源、行情概览和失败信息以统一格式呈现。
- 收敛阶段 2 的资料结果展示，把财联社电报、看盘数据、相关文章和各自时间窗口按固定顺序集中展示。
- 明确失败路径的进展输出，确保在提前停止时仍能留下清晰的阶段结论，而不是零散提示。
- 补充 CLI 输出回归测试，覆盖成功、离线、空资料和阶段 1 失败等关键场景。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整执行进展的终端展示语义，要求阶段输出更紧凑、更有序，并明确资料统计与失败结果的呈现方式。

## Impact

- **Affected code**:
  - `src/cli/ai.py`
  - 可能抽取少量 CLI 输出辅助逻辑到现有 CLI 工具模块
- **Affected tests**:
  - `tests/test_market_summary_cli_flow.py`
- **Affected behaviors**:
  - `wchat ai market-summary`
  - 在线、离线、空资料、提前失败场景下的终端输出
