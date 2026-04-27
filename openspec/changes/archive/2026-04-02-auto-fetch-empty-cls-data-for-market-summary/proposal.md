## Why

当前 `wchat ai market-summary` 在新闻阶段对财联社电报和看盘数据只做本地查询。只要本地库为空，即使在线模式下也会直接显示 `0 条`，要求用户手动再执行 `wchat cls fetch-telegraphs` 或 `wchat cls fetch-watch`，这让市场总结的高频使用路径过于脆弱。

现在需要把在线模式下的 CLS 数据获取收口为“本地优先、查空自动补抓、补抓后回查”的一体化行为，让 `market-summary` 在本地缓存缺失时仍能尽可能完成当天总结，同时保留离线模式和错误状态的可解释性。

## What Changes

- 调整 `market-summary` 的新闻收集逻辑：在线模式下，当本地财联社电报为空时自动按 summary 电报窗口抓取一次，再回查本地数据。
- 调整 `market-summary` 的新闻收集逻辑：在线模式下，当本地看盘数据为空时自动按 summary 看盘窗口抓取一次，再回查本地数据。
- 为 CLS 抓取服务补充更清晰的抓取结果语义，区分“远端无数据”“抓取失败”“抓取成功但仅去重跳过”等情况，避免自动补抓后仍只能显示笼统的 `0 条`。
- 更新 CLI 阶段 2 和生成前预检展示，使用户能看出某个 CLS 来源是直接命中本地，还是经历了自动补抓后成功、为空或失败。
- 保持 `--offline` 模式严格只读本地，不触发任何 CLS 自动补抓。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-summary`: 在线模式下，当财联社电报或看盘数据本地为空时，系统需要自动补抓对应 CLS 数据并回查结果，再决定新闻阶段状态与数量展示。

## Impact

- 受影响代码:
  - `src/services/market_analyzer.py`
  - `src/services/cls_telegraph_service.py`
  - `src/services/cls_watch_service.py`
  - `src/cli/ai.py`
- 受影响测试:
  - `tests/test_news_ingestion.py`
  - `tests/test_market_summary_cli_flow.py`
  - 视实现方式补充 `tests/test_market_analyzer.py`
- 受影响行为:
  - `wchat ai market-summary`
  - `wchat ai market-summary --force`
  - `wchat ai market-summary --offline`
