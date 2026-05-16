## Why

现有 `wchat ai market-summary` 面向单个交易日的市场复盘，重点是行情总览、当日板块强弱、消息催化和次日观察，不适合作为长期跟踪单个或多个板块趋势的工作台。

用户需要以“板块”为主对象建立持续跟踪档案：先发现候选板块，再选择或批量更新板块趋势，并按板块目录保存每日跟踪快照，便于观察板块状态如何随时间变化。

## What Changes

- 新增 `wchat ai sector-trends` 命令组，用于板块趋势发现、初始化、更新、查看和历史回溯。
- 新增板块候选池与跟踪池语义，支持 `candidate`、`tracked`、`inactive`、`ignored` 等状态。
- 支持查看可引入板块：`sector-trends ls` 默认展示已跟踪板块和候选板块，并可按状态、来源、活跃窗口筛选。
- 支持刷新候选板块：`sector-trends discover --days N` 从行情强弱榜、市场缓存、财联社看盘和相关文章线索中发现候选板块。
- 支持初始化板块跟踪：`sector-trends init --sector <板块>` 将候选或手工指定板块纳入正式跟踪。
- 支持单板块趋势更新：`sector-trends update --sector <板块>` 收集该板块近期证据，读取上次跟踪结论，并生成本次趋势更新。
- 支持批量更新：`sector-trends update --all` 逐个更新所有 `tracked` 板块，并提供 `--limit`、`--force`、`--continue-on-error` 等批处理控制。
- 支持以板块为主的文件输出：`output/sector_trends/{板块名}/{YYYY-MM-DD}.md`。
- 支持查看最近一次总结与历史记录：`sector-trends show --sector <板块>` 和 `sector-trends history --sector <板块>`。
- 新增板块去重与归一化策略：优先按稳定代码合并，其次按规范名和显式别名合并；语义相近但不确定的板块只提示，不自动合并。
- 新增板块趋势总结模板，围绕“跟踪结论、相比上次变化、近期表现、催化逻辑、个股联动、趋势研判、后续跟踪条件”输出。

## Capabilities

### New Capabilities

- `sector-trend-tracking`: 以板块为主对象的候选发现、跟踪初始化、趋势更新、批量更新、历史查看、文件输出和去重归一能力。

### Modified Capabilities

- None.

## Impact

- CLI:
  - 新增 `src/cli` 中的 `sector-trends` 子命令组，并注册到 `wchat ai`。
- Services:
  - 新增板块趋势分析服务，负责候选发现、证据收集、状态更新、批量执行和文件持久化。
  - 复用现有 `MarketAnalyzer`、`MarketDataCacheService`、财联社看盘/电报服务和文章查询能力，但不修改 `market-summary` 的职责。
- AI:
  - 新增 `AIProcessor.generate_sector_trend_summary()` 或等价方法，使用独立模板生成单板块趋势跟踪报告。
  - 新增 `templates/sector_trend_summary.md`。
- Data model:
  - 新增板块跟踪档案与趋势总结持久化模型，例如 `TrackedSector`、`SectorTrendSummary`，必要时新增批处理运行记录。
- Output:
  - 新增 `output/sector_trends/{板块名}/{YYYY-MM-DD}.md`。
  - 可选新增批处理汇总 `output/sector_trends/_runs/{YYYY-MM-DD}.md`。
- Tests:
  - 覆盖 CLI 注册、候选发现、板块去重、单板块更新、`--all` 批处理、输出路径和模板结构。
