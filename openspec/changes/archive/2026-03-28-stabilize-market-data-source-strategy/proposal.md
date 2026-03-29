## Why

当前市场数据获取链路能产出指数、成交额、涨跌统计、板块和涨停股，但不同数据项依赖的真实来源并不一致，主/备源策略也主要隐含在 `FinanceClient` 代码里。尤其板块和涨停股仍较依赖东方财富实时 `curl` 路径，而这条路径在非交易时段和部分环境下稳定性偏弱；如果不把 source strategy 单独收口，后续继续修补只会让实现、注释和用户预期继续漂移。

## What Changes

- 为市场数据获取新增显式的“按数据类型划分的 source strategy”能力，明确指数、成交额、涨跌统计、板块、涨停股分别使用什么主源、备源和失败兜底。
- 优先收敛板块和涨停股的稳定性策略，减少对已知不稳定的东方财富 `curl` 主路径的依赖。
- 保持现有统一 contract 不变，但让 source adapter 的选择与降级规则变得可测试、可维护。
- 为实时链路补充针对不同 source path 的契约和回归测试，确保在源失败时输出语义仍然稳定。

## Capabilities

### New Capabilities

- `market-data-source-strategy`: 定义不同市场数据类型的主数据源、备用数据源、降级条件和空值语义

### Modified Capabilities

- `market-summary`: 市场总结依赖的实时市场数据必须来自已定义的 source strategy，并在源降级时保持稳定输出语义

## Impact

- `src/api/finance.py`
- `src/services/market_analyzer.py`
- `tests/test_finance_contracts.py`
- 可能新增针对 source adapter 行为的测试
- `openspec/specs/market-summary/spec.md`
