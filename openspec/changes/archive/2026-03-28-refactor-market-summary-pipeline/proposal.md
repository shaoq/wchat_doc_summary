## Why

当前 `market-summary` 已具备最小可用闭环，但数据链路仍处于半整合状态：CLI、市场数据抓取、缓存服务、财联社电报、财联社看盘数据、文章筛选和模板输入之间存在明显断点与结构漂移。继续在现状上叠加迭代会放大行为不一致、结果不可解释和测试失真的问题，因此需要先完成一次面向 `market-summary` 的流程级重构。

## What Changes

- 修复 `market-summary --list` 历史记录展示分支中的字段错误，恢复历史总结列表能力。
- 统一 `market-summary` 使用的市场数据结构，消除实时抓取、缓存读取、CLI 展示和 AI prompt 之间的字段命名漂移。
- 将市场数据缓存服务接入 `market-summary` 主流程，明确历史交易日、当日交易中、当日收盘后和 `--force` 的缓存策略。
- 重定义 `--offline` 语义为“仅使用本地可用数据生成总结”，优先读取缓存而不是返回空行情结构。
- 将财联社重要电报正式接入 `market-summary` prompt 输入，并补齐财联社看盘数据在总结流程中的接入路径。
- 调整 `market-summary` 对相关文章的筛选方式，从简单的“最近 N 天”改为与交易日相关的可解释时间窗口。
- 补充 `market-summary` 流程级测试，覆盖 `--list`、`--offline`、缓存命中、强制刷新和多数据源整合场景。

## Capabilities

### New Capabilities
- `market-data-cache`: 为市场总结提供统一的市场数据缓存读取、写入和离线回放能力。
- `market-news-aggregation`: 为市场总结统一聚合财联社重要电报、财联社看盘数据和市场相关文章。

### Modified Capabilities
- `market-summary`: 调整交易日总结的数据来源、离线行为、缓存优先级、历史记录展示和文章筛选规则。

## Impact

- **Affected code**:
  - `src/cli.py`
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
  - `src/services/ai_processor.py`
  - `src/api/finance.py`
  - `src/services/cls_watch_service.py`
  - `templates/market_summary.md`
- **Affected tests**:
  - `tests/test_market_summary_logging.py`
  - `tests/test_market_data_cache_service.py`
  - 需要新增 `market-summary` 编排与 prompt 相关测试
- **Affected data/contracts**:
  - `market_data` 返回结构
  - `market-summary` CLI 的 `--offline`、`--list`、`--force` 行为
  - `output/market_summaries/*.md` 的数据来源完整性
