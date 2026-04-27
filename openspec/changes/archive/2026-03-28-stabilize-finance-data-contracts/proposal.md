## Why

当前财经数据获取链路已经覆盖指数、成交额、涨跌统计、板块、涨停股和财联社电报，但这些数据的来源、字段命名、降级方式和聚合边界仍然散落在 `FinanceClient` 及其子数据源中。随着 `market-summary` 和缓存链路继续演进，如果不先稳定财经数据契约，后续每次换数据源或接入新消费方都会放大兼容成本。

## What Changes

- 明确 `FinanceClient` 对外输出的标准财经数据结构，并约束各类数据子模块遵循统一字段命名。
- 收敛指数、成交额、涨跌统计、板块、涨停股和财联社电报的输出 contract 与缺省值语义。
- 明确 `FinanceClient` 的职责边界：负责数据聚合与统一格式，不承担上层业务编排。
- 梳理多数据源降级规则，使“主源失败、备用源接管、全失败兜底”行为可预测。
- 为财经数据层补充契约测试，防止后续切换数据源时破坏上层消费方。

## Capabilities

### New Capabilities
- `finance-data-contracts`: 为财经数据聚合层提供统一的输出契约、缺省值规则和降级行为定义。

### Modified Capabilities
- `market-data-cache`: 调整缓存层所依赖的财经数据字段契约，使缓存读写与财经数据聚合层一致。
- `market-summary`: 调整市场总结对财经数据聚合层输出的依赖方式，统一消费标准字段。

## Impact

- **Affected code**:
  - `src/api/finance.py`
  - `src/api/sector.py`
  - 可能少量影响 `src/services/market_data_cache_service.py`
  - 可能少量影响 `src/services/market_analyzer.py`
  - 可能少量影响 `src/cli.py`
- **Affected tests**:
  - `tests/test_finance_sina.py`
  - 需要新增财经数据 contract 测试
- **Affected data/contracts**:
  - `indices / volume / statistics / sectors / limit_up / cls_telegraph` 的统一字段结构
