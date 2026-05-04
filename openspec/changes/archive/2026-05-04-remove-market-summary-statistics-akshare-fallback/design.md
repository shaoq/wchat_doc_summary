## Context

当前宽度数据策略已经在设计上拆源：

- 成交额主源：交易所官方盘后统计
- 涨跌统计主源：`pytdx`

但实际实现中，涨跌统计仍保留了 `_get_statistics_from_spot_em()` 作为旧链路兜底。该路径通过 AKShare 间接请求东方财富 `push2` 系列接口，而真实运行中这一链路会持续命中 `82.push2.eastmoney.com` 并失败。结果是：

- `market-summary` 每次运行都可能打印无效的旧链路失败日志
- CLI 来源语义仍然保留“涨跌统计旧链路兜底”的分支
- 用户会误以为还有一个有效备用路径存在

换句话说，这不是“保留一个偶尔可用的 fallback”，而是“保留一个长期失效且持续制造噪音的 fallback”。因此本次变更应把涨跌统计 fallback 彻底收口到 `pytdx` 自身质量状态，不再继续尝试 AKShare/东财旧链路。

## Goals / Non-Goals

**Goals:**
- 彻底移除涨跌统计对 AKShare/东财 `spot_em` 的 fallback 请求。
- 保留涨跌统计已有的 `ok / partial / error` 质量状态 contract。
- 让 `pytdx partial` 直接作为最终诊断结果返回，而不是再尝试旧链路。
- 同步收敛 CLI 文案和测试，避免继续暴露“涨跌统计旧链路兜底”来源语义。

**Non-Goals:**
- 不移除成交额的官方源后 AKShare 兜底。
- 不改动涨停股、板块、指数等其他能力里的 AKShare 使用。
- 不在本次变更中重构 `pytdx` 主路径或其 batch/retry 机制。
- 不新增新的涨跌统计备用数据源。

## Decisions

### 1. 涨跌统计 fallback 从“pytdx -> AKShare”收口为“仅 pytdx”

选择：`_get_statistics_with_quality()` 只接受 `pytdx` 返回的三种状态：
- `ok`：直接返回成功结果
- `partial`：直接返回 partial 结果
- `error`：直接返回零值与 error

理由：
- 旧链路在真实环境中已经证明没有工程价值。
- 继续保留只会增加无意义网络请求和误导性日志。
- `partial` 本身已经是一个显式 contract，足以给 CLI 和用户解释“主源不完整”，不需要再赌一个长期失效的 fallback。

备选方案：
- 保留旧链路但默认关闭，仅通过配置启用。放弃原因：配置存在本身就意味着代码和测试要持续维护这条坏链。
- 仅屏蔽失败日志，不移除请求。放弃原因：根本问题不是日志，而是仍在做无价值请求。

### 2. CLI 宽度来源文案同步移除 statistics 的 AKShare 语义

选择：阶段 1 的宽度来源标签不再为涨跌统计保留 `akshare_spot_em` 分支。

理由：
- 去掉实现后，保留这些文案会让 contract 与代码不一致。
- 用户需要看到的是“官方成交额 + pytdx 统计”或“降级为空值 / partial”，而不是一个已失效的旧来源名。

备选方案：
- 保留旧文案作为历史兼容。放弃原因：会让 CLI 输出继续暗示不存在的成功路径。

### 3. 测试契约改为验证“不再尝试旧链路”

选择：将现有“statistics fallback uses akshare”类型测试改成：
- `pytdx partial` 直接返回 partial
- `pytdx error` 直接返回零值
- 不再对 `_get_statistics_from_spot_em()` 做成功兜底断言

理由：
- 测试应反映新的真实 contract，而不是继续绑定已删除路径。

## Risks / Trade-offs

- [当 `pytdx` error 时更快落到零值] → 这是显式收缩坏 fallback 的代价，但当前现实中旧链路本来也没有提供有效成功率。
- [CLI 失去“旧链路兜底”标签后，用户可能觉得容灾变弱] → 应以更准确的 `partial / error` 语义替代虚假的 fallback 成功预期。
- [未来若想重新引入备用源，需要再次改 contract] → 这是合理成本，前提是新备用源必须先证明真实可用。

## Migration Plan

1. 在 `FinanceClient` 中移除涨跌统计对 `_get_statistics_from_spot_em()` 的 fallback 调用。
2. 保留 `pytdx` 的 `ok / partial / error` 质量状态，并以此作为最终返回依据。
3. 调整 CLI 宽度来源文案，删除 statistics 的 AKShare fallback 分支。
4. 更新 contract 和 CLI 测试，覆盖 partial/error 路径，并确认不再依赖旧链路。

## Open Questions

- 是否要在实施时一并删除 `_get_statistics_from_spot_em()`，还是仅停止在涨跌统计路径中调用它。
- 是否要在日志中显式补一句“已禁用涨跌统计旧链路兜底”，帮助后续排查来源变化。
