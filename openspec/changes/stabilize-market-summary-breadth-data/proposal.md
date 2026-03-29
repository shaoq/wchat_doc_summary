## Why

`market-summary` 当前的成交额和涨跌统计并不可靠：主快照源的响应结构已经变化，现有实现会把有效响应误判为空；而备用全市场接口又经常超时，导致命令持续降级成 `0亿` 和 `0/0/0`。继续依赖这条链路会让市场总结看似可执行，但关键宽度数据长期失真，且错误结果还可能被缓存固化。

## What Changes

- 修正全市场股票快照抓取逻辑，兼容当前上游响应结构，并支持分页拿到完整市场样本，而不是只消费单页片段。
- 为成交额和涨跌统计引入显式的数据质量状态，区分“成功拿到完整数据”“只拿到部分样本”“抓取失败后降级”。
- 调整 `market-summary` CLI 展示语义，避免把失败降级后的零值显示成“已获取”。
- 调整市场数据缓存写入门槛，仅在成交额和涨跌统计满足有效性要求时才落库，避免错误零值污染缓存。
- 补充回归测试，覆盖主快照结构变更、分页聚合、状态展示和缓存保护。

## Capabilities

### New Capabilities

无

### Modified Capabilities

- `market-data-source-strategy`: 调整全市场快照策略，使成交额和涨跌统计基于可验证的完整快照结果，并在样本不完整时显式降级。
- `market-summary`: 调整 CLI 对成交额和涨跌统计的展示要求，禁止把失败或部分结果误报为稳定成功。
- `market-data-cache`: 调整缓存写入要求，避免把无效的成交额和涨跌统计结果写入本地缓存。

## Impact

- 受影响代码:
  - `src/api/finance.py`
  - `src/cli/ai.py`
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
- 受影响测试:
  - `tests/test_finance_contracts.py`
  - `tests/test_harden_realtime.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_data_cache_service.py`
- 受影响行为:
  - `wchat ai market-summary`
  - 市场数据缓存写入与命中行为
