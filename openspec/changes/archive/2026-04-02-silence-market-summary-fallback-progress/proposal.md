## Why

`market-summary` 当前虽然在 CLI 上分成“市场数据 -> 新闻数据 -> AI 生成”三阶段，但用户在实际运行时仍会看到来自 `akshare` 的原始分页进度条与终端控制字符。这会打断阶段输出的可读性，也让人难以判断系统是否已经完成全部数据采集、是否已经进入 AI 总结。

进一步分析表明，CLI 的确会在阶段 1 和阶段 2 的异步任务都结束后才进入 AI，但市场宽度数据在备用链路上会并发重复调用 `akshare.stock_zh_a_spot_em()`，导致多条 `tqdm` 进度同时刷屏。继续维持现状会让 `market-summary` 在降级路径下显得“不稳定且不可解释”，排查体验也会持续恶化。

## What Changes

- 明确 `market-summary` 的阶段边界语义：只有在市场数据和新闻数据采集都完成并形成最终输入清单后，CLI 才进入 AI 生成阶段。
- 调整市场宽度数据的备用源策略，让成交额和涨跌统计在需要回退到 `akshare.stock_zh_a_spot_em()` 时共享同一份全市场结果，而不是各自重复抓取。
- 治理 `market-summary` 执行期间的第三方原始进度输出，避免 `akshare` 内部分页 `tqdm` 和终端控制字符直接污染 CLI 阶段日志。
- 补充针对阶段顺序、备用源复用和静默输出的回归测试，确保降级路径仍然可观测且可读。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-summary`: 调整市场总结 CLI 的阶段边界与终端输出要求，确保 AI 阶段只在输入采集完成后开始，并且阶段输出不被第三方原始进度条污染。
- `market-data-source-strategy`: 调整宽度数据备用链路的要求，确保成交额和涨跌统计在降级到全市场备用快照时复用同一次抓取结果，而不是重复触发昂贵且带噪音的全量请求。

## Impact

- 受影响代码:
  - `src/cli/ai.py`
  - `src/api/finance.py`
- 受影响测试:
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_finance_contracts.py`
  - 视实现方式可能补充 `tests/test_market_summary_logging.py`
- 受影响行为:
  - `wchat ai market-summary`
  - `wchat ai market-summary --force`
  - 宽度数据降级到 `akshare` 时的执行耗时、终端输出和阶段可读性
