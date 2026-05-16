## Why

`wchat ai sector-trends groups update --all` 目前在批量执行中主要显示整体 spinner 和最终结果表，用户无法判断当前跑到哪个分组、卡在哪个阶段、哪个成员正在刷新、AI 调用是否在重试。遇到 `API 调用失败 [sector-trend] (尝试 1/4)，1秒后重试: Connection error.` 这类错误时，也缺少分组、成员、阶段、任务类型和重试建议等排障上下文。

本变更要提升分组批量更新的终端体验：提供分组级实时进度、阶段耗时、成员刷新摘要、API 重试诊断和失败后可执行的恢复建议。

## What Changes

- 增强 `groups update --all` 的执行中进度提示，展示当前分组序号、分组名、阶段、成员刷新进展、AI 生成状态和报告保存结果。
- 为批量更新增加默认精简模式、`--verbose` 详细模式和 `--quiet` 静默模式。
- 在批量结果中展示每个分组的状态、成员刷新统计、关键标签、报告路径、耗时和错误摘要。
- 为 API 调用失败和重试提供可诊断上下文，包括阶段、分组、成员、任务类型、尝试次数、等待时间、错误类型和安全的 provider/model 信息。
- 最终失败时输出恢复建议，例如针对单个分组的重试命令、是否建议 `--no-refresh-members`、是否建议 `--force`。
- 引入进度事件或 callback，使 service 能在成员刷新、组级证据、AI 生成、保存等阶段向 CLI 发出可渲染事件。
- 保持报告生成逻辑、数据模型和现有命令语义不变；本变更聚焦终端反馈和诊断。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sector-group-tracking`: 改善分组更新，尤其是 `groups update --all` 的实时进度、错误诊断和重试指导。

## Impact

- Affected code:
  - `src/services/sector_group_service.py`: 为单组和批量组更新增加 progress callback / event emission，并在错误结果中保留结构化诊断。
  - `src/services/sector_trend_service.py`: 如成员刷新调用需要透传 API retry/error context，则增加安全诊断字段或 callback。
  - `src/services/ai_processor.py`: 如 retry 逻辑当前只打印日志，则提供结构化 retry 事件或可捕获诊断。
  - `src/cli/sector_trends.py`: 改造 `groups update --all` 输出，支持默认/verbose/quiet 三种模式。
  - `tests/`: 增加批量进度、错误诊断、retry 展示、verbose/quiet 输出和失败恢复建议测试。
- API / CLI impact:
  - `groups update --all` 增加 `--verbose` 和 `--quiet` 参数。
  - 默认输出更有进度感，但仍不打印报告正文。
- Behavior impact:
  - 不改变分组更新成功/跳过/失败判定。
  - 不改变成员刷新策略。
  - 错误信息更明确，但不得泄露 API key、完整 headers 或完整 prompt。
