## Why

`market-summary` 的涨跌统计当前虽然以 `pytdx` 为主源，但在主路径失败或不完整时仍会尝试 AKShare/东财旧链路兜底。这条兜底链的底层请求长期落到 `82.push2.eastmoney.com`，而实际运行中这条请求一直没有稳定成功过，反而持续制造失败日志和误导性的来源语义。

既然这条旧链路已经无法提供真实的兜底价值，就应当把它从涨跌统计路径中移除，收口成“`pytdx` 成功则用，`pytdx partial` 则保留 partial，`pytdx error` 则直接降级为空值”，避免无意义的坏链路请求继续污染 `market-summary` 体验。

## What Changes

- 移除 `market-summary` 涨跌统计中对 AKShare/东财 `spot_em` 旧链路的 fallback 调用，不再请求 `push2.eastmoney.com` 系列接口作为涨跌统计兜底。
- 调整涨跌统计 contract：`pytdx` 成功时返回成功结果；`pytdx partial` 时直接返回 partial；`pytdx error` 时直接返回零值与错误状态。
- 保留成交额、涨停股、板块等其他能力中仍在使用的 AKShare/东财链路，本次仅收缩“涨跌统计旧链路兜底”。
- 调整 CLI 宽度来源文案与测试，不再展示“涨跌统计旧链路兜底”或“旧链路兜底 (AKShare)”作为涨跌统计来源结果。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-data-source-strategy`: 涨跌统计的 fallback 语义调整为不再尝试 AKShare/东财旧链路，请求失败时只保留 `pytdx` 的 `ok / partial / error` 结果。
- `market-summary`: CLI 的宽度来源展示将不再把 AKShare 作为涨跌统计兜底来源。

## Impact

- 受影响代码:
  - `src/api/finance.py`
  - `src/cli/ai.py`
- 受影响测试:
  - `tests/test_finance_contracts.py`
  - `tests/test_market_summary_cli_flow.py`
- 受影响行为:
  - `wchat ai market-summary`
  - 涨跌统计旧链路失败日志与来源标签
