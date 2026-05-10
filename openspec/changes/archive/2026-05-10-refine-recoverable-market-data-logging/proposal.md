## Why

`market-summary` 当前会把可恢复的单个上游失败以 warning 形式暴露给用户，例如 pytdx 首个主站失败或 Yahoo quote 主源 401，但后续主站或 fallback 已经成功。这会让用户误以为市场数据获取失败，降低阶段日志的可信度。

## What Changes

- 调整市场数据采集日志语义：单个 provider/host 失败但仍会继续尝试时，不再默认输出 warning。
- 在所有同类上游都失败、最终结果不可用或退化为零值合约时，统一输出一次明确的最终失败 warning。
- 保留诊断信息：可恢复尝试失败仍应以 debug 或结构化尝试元数据形式可追踪。
- 保持现有数据 payload、CLI 阶段状态、AI 输入 contract 不变；只优化日志级别与最终失败摘要。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `market-data-source-strategy`: 明确多源/多主站采集中的可恢复尝试失败与最终失败日志边界。
- `market-summary`: 阶段输出应继续以最终归一化状态为准，不被可恢复尝试失败日志干扰；最终失败时应有清晰摘要。

## Impact

- 受影响代码：
  - `src/api/finance.py`
  - `src/cli/ai.py`（如需补充最终失败展示验证）
- 受影响测试：
  - `tests/test_finance_contracts.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_summary_logging.py`
- 外部影响：
  - 默认运行 `wchat ai market-summary` 时，可恢复上游失败不再作为 warning 干扰用户。
  - debug 日志或结构化 metadata 仍可用于排查具体 provider/host 失败。
