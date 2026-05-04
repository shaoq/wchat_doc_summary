## Why

`market-summary` 当前的 A 股数据链路混合了三种不同语义：涨跌统计追求全市场但允许长期 `partial`，板块只保留 `top 5 + bottom 5` 摘要榜单，涨停股固定截断为 20 条。这使得 CLI 虽然能生成总结，但在“尽可能完整”这个目标下，市场宽度输入、涨停池输入和板块输入都存在明显信息损失或质量抖动。

现在需要把这条链路升级为“完整性优先”的市场数据层：涨跌统计要尽量补齐并更准确地区分轻微缺失与明显不完整，涨停股要尽可能获取全量池，板块输入要扩展到 20 个，使 `market-summary` 生成时拿到更接近真实盘面的数据。

## What Changes

- 调整涨跌统计主路径：在 `pytdx` 主源上增加缺失补抓与更细粒度的质量状态，避免“少量缺失长期被视为 partial 且直接透出”。
- 调整涨跌统计缓存门控：允许“近完整”结果写入缓存，仍阻止明显不完整或错误结果污染缓存。
- 调整涨停股 contract：数据层不再固定截断为 20 条，改为尽可能保留全量涨停池；展示层或 AI 输入层如需裁剪，应在更靠后的层完成。
- 调整涨停股兜底语义：当无法获取正式涨停池时，保留快照近似结果，但需要显式区分“正式涨停池”与“近似候选集”。
- 调整板块 contract：从当前 `top 5 + bottom 5` 升级为 `top 10 + bottom 10`，为 `market-summary` 提供更丰富的风格轮动上下文。
- 调整 `market-summary` CLI 与 AI 输入摘要逻辑，使其能正确表达新的宽度质量状态、板块数量和涨停股全量/展示裁剪语义。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-data-source-strategy`: 涨跌统计的完整性保障、涨停股全量获取语义、板块返回数量与回退语义将发生变更。
- `market-data-cache`: 宽度数据缓存门控将从“仅 `ok` 可写”升级为支持更细粒度的有效质量状态，并继续保护已有有效缓存。
- `market-summary`: 市场数据输入的数量与状态表达将改变，CLI 与用于 AI 总结的输入摘要需要同步反映更完整的板块和涨停股数据。

## Impact

- 受影响代码：
  - `src/api/finance.py`
  - `src/services/market_data_cache_service.py`
  - `src/services/market_analyzer.py`
  - `src/services/ai_processor.py`
  - `src/cli/ai.py`
- 受影响测试：
  - `tests/test_finance_contracts.py`
  - `tests/test_market_data_cache_service.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_summary_structure.py`
  - 以及与实时市场数据契约相关的回归测试
- 外部依赖与系统：
  - `pytdx` 涨跌统计主源
  - 交易所官方成交额源
  - `akshare` 板块与涨停池/兜底链路
