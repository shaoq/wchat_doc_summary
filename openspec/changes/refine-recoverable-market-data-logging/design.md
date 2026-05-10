## Context

`market-summary` 的市场数据采集已经具备多源与多主站回退能力：pytdx 会遍历多个行情主站，海外市场上下文会从 `yahoo_quote` 回退到 `yahoo_chart`。当前问题不在数据 contract，而在日志边界：单个上游尝试失败会立即以 warning 输出，即使后续尝试成功，用户也会在成功结果前看到类似“主源失败”的告警。

这次变更应保持现有 payload、缓存和 AI 输入结构不变，只调整默认日志语义，使日志与最终归一化状态一致。

## Goals / Non-Goals

**Goals:**

- 将可恢复的单次 provider/host 失败从默认 warning 降为 debug 或非告警级别。
- 在所有候选上游均失败、最终结果为 `error` 或零值合约时，输出一次聚合 warning。
- 保留排障能力：失败 host、provider、failure_type 和错误摘要仍可通过 debug 日志或结构化 metadata 找到。
- 让 CLI 阶段输出继续以最终状态为准，例如 `近完整`、`fallback`、`error`。

**Non-Goals:**

- 不新增行情数据源。
- 不改变 `global_market_context`、`breadth_quality`、缓存表或 AI prompt 的主结构。
- 不解决 pytdx 或 Yahoo 上游本身的稳定性问题。
- 不把所有采集错误静默吞掉；最终不可用仍必须明确提示。

## Decisions

### 1. 单次尝试失败记录为 debug，最终失败才 warning

pytdx 主站遍历和海外市场 provider chain 都属于“候选尝试”。只要后续还有候选上游，当前候选失败就不应默认输出 warning。

选择：

- pytdx 单个 host 失败：记录到 `attempt_errors`，并使用 debug 日志。
- 海外市场 `yahoo_quote` 或 `yahoo_chart` 单次失败：继续写入 `source_attempts`，日志降级为 debug。
- 所有候选耗尽后：输出一次 warning，包含尝试摘要。

理由：

- warning 应表示用户需要关注的最终降级，而不是正常回退路径中的中间状态。
- 结构化尝试结果已经存在，适合承载详细诊断信息。

备选方案：

- 保留 warning 并在成功后再输出“已恢复”。放弃原因：默认输出仍会制造噪声，且用户需要串联多行日志才能判断结果。

### 2. 最终失败摘要应聚合，而不是重复每个底层异常

最终失败时应输出一条面向排障的摘要，例如：

- `pytdx 涨跌统计全部主站失败: attempts=6, last_error=...`
- `海外市场上下文所有数据源失败: yahoo_quote=unauthorized, yahoo_chart=network_error`

理由：

- 一条聚合 warning 比多条单点 warning 更清晰。
- 聚合摘要能直接表达“已经没有 fallback 可用”。

备选方案：

- 对每个失败上游都保留 warning。放弃原因：这正是当前误导用户的问题来源。

### 3. CLI 阶段状态仍只展示最终归一化结果

`market-summary` 阶段 1 和预检应继续展示最终数据状态，例如 `近完整 (5200/5203)`、`(fallback)` 或 `error`。如果市场数据最终失败，CLI 使用已有 `_status_detail` 展示错误；日志层提供更详细的最终失败摘要。

理由：

- CLI 是用户视角，应该强调最终可用性。
- debug/日志是维护视角，应该保留上游尝试细节。

## Risks / Trade-offs

- [默认日志减少后，临时上游抖动不再显眼] → 通过 debug 日志和 `source_attempts` 保留诊断入口。
- [测试需要捕获日志级别，可能受全局 logging 配置影响] → 使用 `caplog` 或直接测试 logger 调用级别，限定到 `src.api.finance` logger。
- [pytdx 当前 quality 没有保存每个 host 的失败详情] → 仅在函数内部聚合最终 warning，不扩展外部 contract。
- [海外市场 fallback 成功时仍有 info 日志] → 保留或降为 debug 均可，但默认 CLI 已显示 `(fallback)`，实现时应优先避免重复噪声。
