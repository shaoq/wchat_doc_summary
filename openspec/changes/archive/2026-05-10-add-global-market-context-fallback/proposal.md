## Why

当前海外市场上下文依赖单一 Yahoo quote 接口，`2026-05-07` 已实测出现稳定的 `401 Unauthorized`。这意味着 `market-summary` 的海外市场证据会在上游策略变化时整体失效，现有实现虽然能降级报错，但缺少可恢复的数据源路径和更细粒度的失败语义。

## What Changes

- 为海外市场上下文采集增加声明式多源回退策略，避免单一上游拒绝访问时整块上下文直接失效。
- 标准化海外市场上游失败分类，区分 `unauthorized`、`rate_limited`、`empty`、`malformed`、`network_error` 等结果，便于 CLI、日志和缓存复用。
- 扩展海外市场上下文 contract，记录最终命中的 `source`、尝试序列和降级状态，使下游知道“数据来自哪里、失败发生在哪一层”。
- 调整缓存写入策略：对同一目标交易日已有成功或部分成功海外上下文时，失败性重抓不应盲目覆盖更好的缓存。
- 扩展 `market-summary` 的阶段展示和 prompt 输入，让用户与模型看到海外市场上下文是否来自 fallback，以及当前缺口是否由上游拒绝访问导致。
- 补充回归测试，覆盖上游 401、多源回退命中、缓存保护和 CLI 展示。

## Capabilities

### New Capabilities
- `global-market-context-fallback`: 为海外市场上下文定义多源抓取顺序、失败分类、命中来源和降级元数据。

### Modified Capabilities
- `market-summary`: 海外市场上下文展示与 AI 输入需要暴露 fallback 来源、上游失败类型和更细粒度的缺口提示。
- `market-data-cache`: 海外市场上下文缓存需要保存来源与尝试元数据，并避免失败性刷新覆盖更优缓存。

## Impact

- 受影响代码：
  - `src/api/finance.py`
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
  - `src/services/ai_processor.py`
  - `src/cli/ai.py`
- 受影响测试：
  - `tests/test_finance_contracts.py`
  - `tests/test_market_data_cache_service.py`
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_summary_structure.py`
- 外部影响：
  - 海外市场上下文将不再把 Yahoo 视为唯一上游
  - 该变更默认建立在 `add-us-market-context-to-market-summary` 的 contract 已经落地的前提上
