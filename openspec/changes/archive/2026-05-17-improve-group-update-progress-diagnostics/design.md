## Context

单分组 `groups update --group` 已经使用阶段式输出，能展示成员检查、成员刷新、证据收集、AI 生成和保存结果。批量 `groups update --all` 仍以服务层黑盒调用为主，执行期间没有逐个分组的进度事件，用户只能等待最终汇总。

组级批量更新可能包含多个耗时点：

```text
batch
  -> group 1
     -> member refresh N times
     -> group evidence
     -> group AI summary
     -> save report
  -> group 2
  -> ...
```

其中成员刷新和 AI 调用都可能发生网络错误、重试或超时。如果终端只显示 spinner，用户无法判断是正常耗时、网络异常、AI 重试，还是某个成员卡住。

## Goals / Non-Goals

**Goals:**

- 让 `groups update --all` 在执行中显示当前进度，而不是只在完成后输出。
- 明确展示当前分组、当前阶段、当前成员、阶段耗时和整体耗时。
- 对 API 调用失败和重试展示足够上下文，帮助用户判断是否等待、重试或调整参数。
- 在最终失败或部分失败时提供可执行重试命令。
- 支持默认精简输出、`--verbose` 详细输出、`--quiet` 脚本友好输出。
- 保持报告正文不默认打印。

**Non-Goals:**

- 不改变 AI 生成内容。
- 不改变分组更新业务规则、成员刷新策略或报告保存路径。
- 不暴露 API key、完整 request headers、完整 prompt 或敏感配置。
- 不在第一版实现后台任务队列或 Web UI。

## Decisions

### 1. 用进度事件解耦服务和 CLI

新增进度事件结构，例如：

```text
GroupUpdateProgressEvent
- type
- group_name
- group_index
- group_total
- stage
- member_name
- action
- attempt
- max_attempts
- retry_delay
- error
- elapsed
- output_path
- labels
```

事件类型可覆盖：

```text
batch_start
group_start
member_check_done
member_refresh_start
member_refresh_retry
member_refresh_done
member_refresh_failed
group_evidence_start
group_ai_start
group_ai_retry
group_ai_done
group_saved
group_skipped
group_failed
batch_done
```

理由：

- 服务层保留业务流程，CLI 只负责渲染。
- 后续可复用于日志、测试或其他 UI。
- 避免 CLI 为了进度展示复制批量更新业务逻辑。

替代方案：

- CLI 自己循环所有分组并打印。实现快，但会把服务层批量逻辑拆到 CLI，后续维护成本高。

### 2. 默认模式显示“分组级进度 + 完成摘要”

默认输出示例：

```text
批量更新分组趋势
交易日: 2026-05-15
目标: active 分组
数量: 6
成员刷新: 默认刷新缺失 tracked 成员

[1/6] 人形机器人链
  成员: tracked 2, candidate 0
  刷新成员: 1 已更新, 1 今日已有
  生成组级总结: AI 生成中...
  v 已更新 | 状态: 主线启动 | 报告: output/sector_groups/人形机器人链/2026-05-15.md
  耗时: 38.2s
```

默认模式不逐条展示所有细节，只展示当前阶段和每组结果。

### 3. `--verbose` 展示成员和 retry 细节

verbose 输出应包括：

- 每个成员刷新动作。
- candidate / inactive / has_report 的跳过原因。
- API retry 的阶段、任务类型、尝试次数、等待时间和错误摘要。
- 安全的 provider/model/base_url host 信息。
- 每个阶段耗时。

但仍不输出完整 prompt、headers 或 API key。

### 4. `--quiet` 保持脚本友好

quiet 模式只输出最终汇总和失败行，减少 CI 或脚本日志噪声：

```text
success=5 skipped=1 failed=1 member_refresh_failed=2
failed: 人形机器人链 / 智能机器 / sector-trend / Connection error
```

### 5. API 错误诊断分层展示

默认 retry 信息：

```text
! API 调用失败，准备重试
  阶段: 成员板块刷新
  分组: 人形机器人链
  成员: 智能机器
  任务: sector-trend
  尝试: 1/4
  等待: 1s
  错误: Connection error
```

verbose 补充：

```text
provider: openai-compatible
model: gpt-4.1
base_url: https://api.example.com/v1
exception: APIConnectionError
elapsed: 12.4s
```

最终失败应追加恢复建议：

```text
可重试:
  wchat ai sector-trends groups update --group 人形机器人链 --no-refresh-members --force
```

如果失败发生在组级总结：

```text
wchat ai sector-trends groups update --group 人形机器人链 --force
```

### 6. 结构化错误结果进入最终汇总

服务返回的 `results` 中应保留简洁诊断：

```json
{
  "action": "failed",
  "group_name": "人形机器人链",
  "stage": "member_refresh",
  "member_name": "智能机器",
  "task": "sector-trend",
  "error": "Connection error",
  "attempts": 4,
  "retryable": true,
  "suggested_command": "wchat ai sector-trends groups update --group 人形机器人链 --no-refresh-members --force"
}
```

这样最终表格和测试都能稳定验证。

## Risks / Trade-offs

- [Risk] 输出过多影响可读性 -> 默认精简，详细信息放到 `--verbose`。
- [Risk] 进度事件增加服务复杂度 -> 使用小型 dataclass/dict 事件，不引入大型框架。
- [Risk] retry 信息泄露敏感配置 -> 只显示 provider/model/base_url host，不显示 key、headers、prompt。
- [Risk] quiet 模式隐藏重要错误 -> quiet 仍输出失败摘要和最终 exit/error 状态相关信息。
- [Risk] AI retry 逻辑分散在不同服务 -> 先统一事件字段，再逐步接入 sector-trend 和 group-trend 两类调用。

## Migration Plan

1. 保持现有 `groups update --all` 命令可用。
2. 增加 `--verbose` / `--quiet` 参数，默认输出升级但不破坏现有业务行为。
3. 先接入组级批量更新事件，再接入成员刷新和 AI retry 事件。
4. 没有 progress callback 时，服务保持现有行为。
5. 回滚时移除 CLI 渲染和事件参数，不影响已生成报告。

## Open Questions

- 是否需要在 API retry 时实时刷新同一行，还是追加日志行更便于回看？
- 默认模式是否展示 provider/model，还是只在 verbose 模式展示？
- 批量失败时是否应返回非 0 exit code，还是继续保持当前 CLI 行为？
