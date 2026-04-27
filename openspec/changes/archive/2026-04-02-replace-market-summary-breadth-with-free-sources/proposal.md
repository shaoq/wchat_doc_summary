## Why

`market-summary` 当前最脆弱的环节是成交额和涨跌统计：它们依赖东方财富全市场快照与其备用链路，而这条链路已经多次出现空响应、超时和代理兼容性问题。既然本次目标明确为“完全免费优先”，就需要把宽度数据改成优先使用免费且不以东方财富为单点依赖的组合源，而不是继续围绕东财做修补。

## What Changes

- 将成交额和涨跌统计的主数据源策略从“东方财富快照优先”改为“免费优先的宽度数据适配器优先”，以 `mootdx` 作为新的主宽度源。
- 保持指数数据继续优先使用腾讯财经，保留其现有稳定专用链路。
- 保持板块和涨停股继续沿用现有免费策略，不在本次变更中重写其主源，只在设计中明确它们仍属于增强信息而非本次主替换目标。
- 为宽度数据增加更明确的来源与降级语义，使调用方能区分“来自免费主源的成功结果”和“回退到旧链路或零值 contract 的失败结果”。
- 补充依赖、契约测试和回归测试，确保新的免费优先策略不会破坏现有缓存结构和 CLI 汇总流程。

## Capabilities

### New Capabilities

无

### Modified Capabilities

- `market-data-source-strategy`: 调整成交额与涨跌统计的主源与回退顺序，使其优先使用免费且不依赖东方财富快照的宽度数据策略。
- `market-summary`: 调整阶段 1 的来源语义与宽度数据展示要求，使输出能够反映免费优先策略及其降级结果。

## Impact

- 受影响代码:
  - `src/api/finance.py`
  - `src/cli/ai.py`
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
  - `requirements.txt`
- 受影响测试:
  - `tests/test_finance_contracts.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_data_cache_service.py`
  - 可能新增 `mootdx` 适配器相关测试
- 受影响依赖:
  - 新增免费行情依赖 `mootdx`
- 受影响行为:
  - `wchat ai market-summary` 的成交额与涨跌统计来源、降级路径与来源展示
