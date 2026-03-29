## Context

`market-summary` 在上一轮重构中已经补齐了缓存、新闻聚合、时间窗口和模板输入，但当前仍有执行层面的偏差：

- CLI 已解析 `trade_date` 和 `force`，但调用 `collect_market_data()` 时没有传入这两个参数
- `offline` 模式下，如果没有本地缓存，服务层会返回错误状态，但 CLI 仍继续进入后续生成流程
- 现有测试主要验证帮助信息、新闻聚合和格式化函数，没有覆盖 CLI 对关键参数的真实编排行为

这些问题不需要再次做大重构，但需要一次小范围 follow-up 来让 CLI 行为真正和规格对齐。

## Goals / Non-Goals

**Goals:**
- 让 CLI 将 `trade_date` 和 `force` 正确传入市场数据收集链路
- 收敛 `offline` 无缓存场景下的用户可见行为
- 用流程级测试锁住 `market-summary` 的关键参数语义

**Non-Goals:**
- 不重新设计 `market-summary` 整体架构
- 不修改新闻聚合或模板格式化的主要逻辑
- 不改变 `market_data` 的数据结构 contract

## Decisions

### 1. CLI 参数必须显式透传给 `collect_market_data()`

`market-summary` CLI 解析出的 `trade_date` 与 `force` 必须在获取市场数据时显式传入服务层，不能再让服务层自行推断默认值。

备选方案：
- 继续依赖服务层默认值。放弃原因：这正是当前行为偏差的根因。

### 2. Offline 无缓存时以“明确失败并停止”为默认行为

当离线模式下无可用本地市场数据时，CLI 应明确提示并停止后续 AI 生成流程。这比继续生成一个缺失核心行情输入的总结更符合当前提案和用户预期。

备选方案：
- 允许继续生成但附加 warning。放弃原因：会弱化 offline 语义，且难以界定生成结果的可用性。

### 3. CLI 流程测试覆盖关键参数分支

需要补充真实 CLI 行为测试，而不是只验证 `--help` 或底层服务方法。重点覆盖：

- `--date`
- `--force`
- `--offline`
- `--list`

## Risks / Trade-offs

- [offline 行为改为停止后，用户可能觉得更严格] → 通过明确错误提示说明原因，减少误解
- [CLI 测试可能需要较多 mock 编排] → 聚焦关键行为断言，不追求覆盖所有输出细节
- [若服务层将来再改默认行为，CLI 测试会更敏感] → 这正是需要的回归保护

## Migration Plan

1. 修正 CLI 调用 `collect_market_data()` 的参数透传
2. 收敛 offline 无缓存时的退出逻辑
3. 增加 CLI 流程测试与调用参数断言
4. 验证 `--date`、`--force`、`--offline`、`--list` 四个关键分支

回滚策略：
- 若 CLI 行为调整存在争议，可先保留参数透传修复，仅回退 offline 失败时的停止策略

## Open Questions

- 当前 `offline` 无缓存时，是否需要非零退出码，还是仅打印错误信息后正常结束
