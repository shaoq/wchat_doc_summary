## Why

当前市场数据链路已经能支撑“今天 / 最近一个交易日”的市场总结，但实时取数层仍有几处会直接影响可用性和稳定性的实现缺口：板块缓存键不稳定、成交额与涨跌统计重复扫描全市场、以及个别数据项在“最近一个交易日”场景下仍可能与目标日期错位。如果不先收口这些问题，市场总结虽然能跑，但性能、缓存命中率和结果一致性会持续不稳定。

## What Changes

- 收敛实时市场数据抓取路径，确保“今天 / 最近一个交易日”场景下所有市场数据项使用同一轮目标日期语义。
- 合并成交额与涨跌统计对全市场股票列表的重复扫描，降低实时取数成本。
- 修正板块缓存写入所依赖的唯一键策略，避免板块数据因空代码或不稳定标识导致缓存冲突。
- 调整涨停股取数逻辑，使其至少对齐到当前总结所使用的目标交易日，而不是固定绑定系统当天。
- 明确并补足实时取数层的重试、降级和短时复用策略，避免代码中存在“声明了能力但实际未接入”的状态。
- 为以上行为补充针对实时链路的回归测试，覆盖性能复用、最近交易日语义和缓存稳定性。

## Capabilities

### New Capabilities
- `realtime-market-data-fetching`: 为市场总结提供面向“今天 / 最近一个交易日”的一致、可复用、可降级的实时市场数据抓取能力。

### Modified Capabilities
- `market-data-cache`: 调整实时市场数据写入缓存时的标识稳定性和落库约束，确保缓存可以稳定保存并回放实时取数结果。
- `market-summary`: 调整最近交易日市场总结对实时市场数据的依赖方式，确保各数据项与目标交易日语义一致。

## Impact

- **Affected code**:
  - `src/api/finance.py`
  - `src/api/sector.py`
  - `src/services/market_data_cache_service.py`
  - `src/services/market_analyzer.py`
  - 可能少量影响 `src/models/schema.py` 对板块缓存标识的使用方式
- **Affected tests**:
  - `tests/test_finance_contracts.py`
  - `tests/test_market_data_cache_service.py`
  - `tests/test_market_summary_cli_flow.py`
  - 需要新增实时取数复用与最近交易日语义测试
- **Affected behaviors**:
  - `wchat ai market-summary`
  - `wchat ai market-summary --date <最近交易日>`
  - 市场数据缓存写入与命中行为
