## Why

`market-summary` 主链路已经能跑通，但执行层还有几处会持续影响稳定性和可解释性：前置参数错误会被 AI 初始化抢先打断、新闻阶段对部分失败缺少明确语义、总结保存存在数据库与文件落盘失配风险，而且市场数据策略逻辑分散在多个入口。继续在这些边界上堆叠功能，会让命令“能运行”但不够稳，也不够容易维护。

## What Changes

- 调整 `market-summary` 的前置校验顺序，确保日期解析等本地错误在 AI 相关依赖初始化前完成。
- 收紧新闻聚合阶段的执行语义和 CLI 展示语义，让“成功 / 部分退化 / 失败”能够被明确区分。
- 明确市场总结保存的一致性语义，避免数据库记录与 Markdown 文件状态失配。
- 收敛市场数据获取策略入口，减少 `market-summary` 对缓存/在线/强刷规则的重复表达。
- 为上述边界场景补充流程与回归测试。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-summary`: 命令执行前置校验、新闻阶段状态表达、总结保存完成语义和市场数据获取策略需要更稳定一致。

## Impact

- `src/cli/ai.py`
- `src/services/market_analyzer.py`
- `src/services/market_data_cache_service.py`
- `tests/test_market_summary_cli_flow.py`
- 可能补充 `tests/test_historical_market_data.py` 与 `tests/test_market_analyzer.py`
