## Why

`market-summary` 的免费宽度方案已经验证出两个关键问题：`mootdx` 并不能稳定提供干净、完整且可验证的 A 股宽度样本，而它背后的 `tdxpy` 证券类型识别与自动初始化流程也会持续引入噪音和错误口径。既然目标仍然是“免费优先”，就需要换成更接近业务语义的数据拆分方案：成交额使用交易所官方盘后统计，涨跌家数使用 `pytdx` 直接拉取 A 股 quotes 并自行聚合。

## What Changes

- 将成交额主数据源从“实时全市场快照推导”改为“交易所官方盘后成交统计”，分别获取上交所和深交所股票成交概况并汇总两市成交额。
- 将涨跌统计主数据源改为 `pytdx`，基于明确维护的 A 股 universe 拉取 quotes，再按 `price` 与 `last_close` 计算上涨、下跌、平盘家数。
- 保持指数继续优先使用腾讯财经，保持板块与涨停股继续沿用现有免费链路，不在本次变更中重写这些数据类型。
- 为宽度数据补充更准确的来源语义，区分“官方成交额 + pytdx 涨跌统计命中”“旧免费链路兜底”“失败降级为空值”。
- 将 `mootdx` 从宽度主路径中移除，避免继续把不稳定的证券列表 + 批量 quotes 方案当作主成功路径。

## Capabilities

### New Capabilities

无

### Modified Capabilities

- `market-data-source-strategy`: 调整成交额与涨跌统计的免费主源策略，改为“官方成交额 + pytdx 涨跌统计 + 旧链路兜底”。
- `market-summary`: 调整阶段 1 的来源语义与宽度数据展示要求，使输出能反映官方成交额、pytdx 统计与兜底/降级结果。

## Impact

- 受影响代码:
  - `src/api/finance.py`
  - `src/cli/ai.py`
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
  - `requirements.txt`
  - `pyproject.toml`
- 受影响测试:
  - `tests/test_finance_contracts.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_data_cache_service.py`
  - 可能新增交易所官方成交额解析与 `pytdx` universe 相关测试
- 受影响依赖:
  - 新增免费行情依赖 `pytdx`
  - `mootdx` 不再作为宽度主路径依赖
- 受影响行为:
  - `wchat ai market-summary` 的成交额与涨跌统计来源、质量判断和阶段 1 来源展示
