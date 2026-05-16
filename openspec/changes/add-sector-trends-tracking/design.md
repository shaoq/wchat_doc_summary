## Context

`wchat ai market-summary` 当前围绕单一交易日生成 A 股市场复盘。它的板块信息来自当日强弱榜、涨停、财联社看盘/电报和本地文章，但输出对象仍然是“某日市场总结”，不是“某个板块的持续跟踪档案”。

板块趋势跟踪需要不同的主轴：

- 主对象是板块，而不是日期。
- 日期是该板块的一次更新快照。
- `--all` 是对已跟踪板块逐个执行单板块更新，不是把所有板块混合生成一份大报告。
- 候选板块必须可见，用户需要知道哪些板块可以引入跟踪池。
- 板块去重必须谨慎，避免把大板块和有独立交易价值的细分方向误合并。

现有可复用数据源包括：

- `MarketSector` / `market_sectors`: 历史强弱榜缓存。
- `FinanceClient.get_sector_data()`: 当前板块涨跌数据，现有 contract 返回 `top_sectors` 和 `bottom_sectors`。
- 财联社看盘数据: 已包含 `sectors` 字段，可发现盘中高频题材。
- 财联社电报和本地文章: 可作为板块催化和观点补充。
- `AIProcessor`: 可新增独立模板和方法，不复用 `market_summary` 模板。

## Goals / Non-Goals

**Goals:**

- 新增 `wchat ai sector-trends` 命令组，覆盖候选发现、查看、初始化、单板块更新、批量更新、最近总结查看和历史查看。
- 建立板块候选池和跟踪池，区分 `candidate`、`tracked`、`inactive`、`ignored`。
- 将文件输出改为板块优先：`output/sector_trends/{板块名}/{YYYY-MM-DD}.md`。
- 生成以“长期跟踪”为目标的单板块趋势模板，重点呈现本次结论、相比上次变化、证据、趋势研判和后续验证条件。
- 支持基于代码、规范名、别名的高置信去重；语义相近但不确定的板块只提示，不自动合并。
- `update --all` 默认只处理 `tracked` 板块，并以逐板块方式执行，提供成本和失败控制。

**Non-Goals:**

- 不修改 `wchat ai market-summary` 的现有输出结构、模板和持久化语义。
- 第一版不承诺覆盖全市场所有概念/行业板块，只承诺覆盖系统发现或用户初始化的候选/跟踪板块。
- 第一版不做复杂行业知识图谱或 LLM 自动语义合并。
- 第一版不要求实时盘中持续刷新，只支持命令触发式发现和更新。
- 第一版不把所有候选板块默认纳入 `--all`，避免 AI 成本不可控。

## Decisions

### 1. 使用 `sector-trends` 命令组而不是单一命令

选择：

```text
wchat ai sector-trends ls
wchat ai sector-trends discover
wchat ai sector-trends init
wchat ai sector-trends update
wchat ai sector-trends show
wchat ai sector-trends history
```

理由：

- `ls`、`discover`、`init`、`update` 和 `show/history` 是不同生命周期操作。
- 单一命令挂大量参数会让 `--all`、`--sector`、`--status`、`--source` 等语义互相干扰。
- 命令组更接近“板块趋势工作台”。

替代方案：

- 单命令 `wchat ai sector-trends --sector 半导体 --all --list`。该方案实现更少文件，但用户语义不清晰，后续扩展也更困难。

### 2. 板块优先的输出目录

选择：

```text
output/sector_trends/{sector_name}/{YYYY-MM-DD}.md
```

理由：

- 用户目标是“跟踪板块”，板块应该是第一层目录。
- `history --sector 半导体` 可以直接读取该目录形成时间线。
- `--all` 的结果仍然是多个板块各自的日快照，而不是日期目录下的一次性报告。

替代方案：

```text
output/sector_trends/{YYYY-MM-DD}/{sector_name}.md
```

该方案适合日度批处理，但弱化了板块长期档案。

### 3. 新增板块档案和趋势总结模型

建议新增：

```text
TrackedSector
- id
- canonical_name
- sector_code
- aliases
- source_codes
- category
- status
- source
- first_seen_date
- last_seen_date
- last_updated_date
- discovery_reason
- created_at
- updated_at

SectorTrendSummary
- id
- sector_id
- sector_name
- sector_code
- end_date
- window_days
- trend_status
- strength_level
- action_bias
- judgement
- content
- evidence_json
- output_path
- created_at
- updated_at
```

理由：

- `TrackedSector` 承载长期板块档案、候选状态、别名和来源。
- `SectorTrendSummary` 承载每次更新快照，可回放历史判断。
- 不复用 `MarketSummary`，避免单日市场总结和板块趋势总结共享错误语义。

### 4. 候选发现和初始化分离

发现流程：

```text
discover --days N
  -> 扫描近 N 日行情强弱榜、市场缓存、财联社看盘、文章线索
  -> 归一化名称
  -> 按发现规则计算候选
  -> 写入或更新 candidate
```

初始化流程：

```text
init --sector <name>
  -> 找到候选或创建手工板块
  -> 状态改为 tracked
  -> 不强制生成 AI 总结
```

`update --sector <name>` 可以自动初始化缺失板块为 `tracked`，然后生成第一份趋势总结。

理由：

- 用户可以先浏览 candidate，再决定纳入跟踪。
- `update --sector` 保持高效路径，不要求先手动 init。
- `--all` 默认只跑 `tracked`，避免候选池自动消耗 AI 调用。

### 5. 去重只做高置信合并

自动合并顺序：

1. 稳定代码相同。
2. 规范名完全相同。
3. 命中已有显式别名。

不自动合并：

- 文本相似但语义不完全等价。
- 大板块与细分方向，例如“半导体 / AI芯片 / 先进封装”。
- 同一产业链上下游，例如“机器人 / 减速器 / 传感器”。

这些只在 `ls` 中作为 `possible_matches` 或提示展示，由用户通过后续命令显式合并或添加别名。

理由：

- 板块趋势跟踪中，细分方向经常有独立行情。误合并会损失分析价值。
- 第一版保持规则可解释，避免 LLM 语义归并带来的不可控结果。

### 6. 单板块趋势更新读取上次总结

`update --sector 半导体` 应读取该板块最近一次 `SectorTrendSummary`，并把上次状态、结论、确认信号、失效条件与本次新增证据一起传给 AI。

首次更新时模板降级为“首次建档”，不要求输出“相比上次变化”。

理由：

- 跟踪的核心价值是状态变化，而不是每次孤立重写。
- 可让输出明确描述“由低位启动转为分歧中继”等变化。

### 7. AI 模板强制输出结构化标签

模板要求输出：

```text
trend_status: 主线加强 / 主线延续 / 分歧中继 / 低位启动 / 轮动补涨 / 短线脉冲 / 高位退潮 / 暂无趋势
strength_level: 强 / 中 / 弱
action_bias: 跟踪 / 观察 / 回避
```

报告章节：

1. 跟踪结论
2. 相比上次更新的变化
3. 近期板块表现
4. 催化与逻辑
5. 个股联动与辨识度
6. 趋势研判
7. 后续跟踪条件

理由：

- `ls`、`show`、`history` 需要结构化状态展示。
- 固定章节避免变成泛化市场评论。

## Risks / Trade-offs

- [Risk] 现有 `market_sectors` 只缓存强弱榜，不是全市场全量板块快照 → 第一版明确为“系统发现/活跃板块跟踪”，不承诺全市场覆盖；后续可新增全量板块快照能力。
- [Risk] `--all` 成本和耗时较高 → 默认只跑 `tracked`，支持 `--limit`、跳过已更新、`--continue-on-error`，并输出批处理汇总。
- [Risk] 板块名称歧义导致误合并 → 只自动执行高置信合并，低置信相似项仅提示人工确认。
- [Risk] 文件路径包含中文或特殊字符 → 实现时需要稳定的路径安全转换，并保留展示名到输出路径的映射。
- [Risk] 单板块证据不足时 AI 可能强行下判断 → 模板和服务层都必须提供数据缺口提示，要求输出“暂无趋势”或“观察”。
- [Risk] 候选池过大影响可读性 → `ls` 默认按活跃度、最近出现时间排序，并支持 `--status`、`--source`、`--active-days`、`--limit`。
