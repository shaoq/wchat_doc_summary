## Why

当前工程的整体结构已经基本对齐近期重构方向，但仍存在几处“规格已声明、实现未闭环”的关键缺口：历史日期市场总结会混入当日行情、交易日判断与 A 股语义不一致、财联社新闻链路停留在本地读取侧、以及模块化 CLI 没有保住 `python -m src.cli` 入口。继续在这些偏差上叠加功能，会让缓存、总结结果和用户可见行为持续背离当前 OpenSpec 预期，因此需要先做一次面向规格一致性的收口变更。

## What Changes

- 修正 `market-summary` 在历史交易日、缓存未命中和 `--force` 场景下的市场数据语义，禁止将“当前行情”错误归属到目标交易日。
- 收敛 A 股交易日判断规则，避免将调休工作日周末误判为交易日，并让默认交易日选择与文章窗口计算基于同一语义。
- 将相关文章选择切换到精确的交易日时间窗口，并让 CLI 展示的时间窗口与实际筛选窗口一致。
- 补齐财联社重要电报和看盘数据的本地入库闭环，使 `market-summary` 使用的本地新闻源具备稳定的数据来源，而不是长期依赖空表读取。
- 修复模块化 CLI 后 `python -m src.cli` 不可执行的问题，恢复规格承诺的模块入口兼容性。
- 为以上行为补充针对规格语义的回归测试，覆盖历史日期、交易日边界、新闻入库与 CLI 入口。

## Capabilities

### New Capabilities
- `market-news-ingestion`: 为市场总结提供可持续的财联社电报与看盘数据本地入库能力，保证本地聚合输入具备稳定来源。
- `cli-entrypoint-compatibility`: 保证模块化 CLI 在安装脚本入口和 `python -m src.cli` 模块入口下都可用。

### Modified Capabilities
- `market-summary`: 修正交易日语义、历史日期总结的数据基准、精确文章窗口和相关 CLI 展示行为。
- `market-data-cache`: 修正历史交易日与强制刷新场景下的缓存语义，确保缓存内容与目标交易日一致。

## Impact

- **Affected code**:
  - `src/services/market_analyzer.py`
  - `src/services/market_data_cache_service.py`
  - `src/api/finance.py`
  - `src/services/cls_telegraph_service.py`
  - `src/services/cls_watch_service.py`
  - `src/api/cls_roll.py`
  - `src/api/cls_watch.py`
  - `src/cli/__init__.py`
  - `src/cli.py`
  - 需要新增 `src/cli/__main__.py` 或等价模块入口
- **Affected tests**:
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_analyzer.py`
  - `tests/test_market_data_cache_service.py`
  - `tests/test_cli_commands.py`
  - 需要新增新闻入库闭环与模块入口测试
- **Affected behaviors**:
  - `wchat ai market-summary`
  - `wchat ai market-summary --date`
  - `wchat ai market-summary --force`
  - `wchat ai market-summary --offline`
  - `python -m src.cli --help`
  - `python -m src.cli ai --help`
