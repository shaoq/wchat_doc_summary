## Context

`add-us-market-context-to-market-summary` 已经把海外市场上下文接入 `market-summary` 主链路，但当前实现把 `query1.finance.yahoo.com/v7/finance/quote` 作为唯一上游。实测在 `2026-05-07` 该接口返回 `401 Unauthorized`，导致在线模式的海外市场上下文稳定降级为错误状态。

这次变更不是重新设计海外市场 contract，而是在既有 contract 基础上补“可靠性层”。它横跨行情抓取、缓存保护、CLI 表达和 prompt 约束，属于典型的跨模块行为修复。约束有三点：

- 不能把临时上游异常直接暴露成“无海外市场影响”，必须明确区分“数据缺失”和“上游拒绝访问”。
- 不能因为一次失败性重抓，把同一目标交易日已有的较好海外上下文缓存覆盖掉。
- 不能让 fallback 改变下游 contract 的主结构，下游仍应消费统一的 `global_market_context`。

## Goals / Non-Goals

**Goals:**
- 为海外市场上下文定义稳定的多源回退顺序，并对每次尝试输出统一结果语义。
- 在保持现有 `global_market_context` 主结构不变的前提下，补充 `source`、`source_attempts`、失败类型等元数据。
- 让在线抓取、缓存回放、CLI 展示和 AI prompt 都能识别“主源失败但 fallback 成功”和“所有上游都失败”这两类情况。
- 保护已有缓存，避免错误状态覆盖更高质量的历史结果。

**Non-Goals:**
- 不在本次设计中引入付费商业行情依赖或复杂凭证管理。
- 不扩大海外市场信号集合，仍沿用上一变更定义的核心指标集合。
- 不改变历史交易日与 `--offline` 的基本策略，仍以缓存回放优先。

## Decisions

### 1. 采用“提供者列表 + 统一标准化层”，而不是在单一 Yahoo 调用上继续修补请求头

设计选择：

- 在 `src/api/finance.py` 内为海外市场上下文增加显式 provider 列表，例如 `yahoo_quote -> fallback_provider_1 -> fallback_provider_2`。
- 每个 provider 负责自己的抓取和原始字段解析，但输出统一的尝试结果结构：
  - `status`: `ok | partial | error`
  - `failure_type`: `unauthorized | rate_limited | empty | malformed | network_error | none`
  - `source`: provider 名称
  - `rows` 或标准化后的中间结果
- 聚合层按顺序短路：一旦得到可消费结果即停止后续 provider。

理由：

- Yahoo 已经出现明确的权限拒绝，继续堆请求头只能得到脆弱修补。
- provider 抽象能把“上游切换”限制在采集层，不把变化扩散到 CLI、缓存和 prompt。

备选方案：

- 继续仅使用 Yahoo，通过 cookie、crumb 或更复杂请求头规避。放弃原因：依赖非稳定网页行为，维护成本高，且仍然是单点。

### 2. 在现有 `global_market_context` 上追加来源与尝试元数据，而不是重做主 payload

设计选择：

- 保留现有顶层字段与 `us_market` 主体结构。
- 增加以下元数据字段：
  - `source`: 最终命中的 provider，若全部失败则为最后一个尝试的 provider 或 `none`
  - `source_attempts`: 顺序数组，记录每个 provider 的 `source/status/failure_type/message`
  - `degraded`: 布尔值，表示是否发生了主源失败后 fallback 命中
- `message` 仍作为面向 CLI/日志的摘要，但不再承担完整失败语义。

理由：

- 现有下游已经消费 `status/message/source`，增量扩展比重构 payload 更稳妥。
- `source_attempts` 可以同时服务 CLI、日志和诊断测试，避免到处拼接异常字符串。

备选方案：

- 仅更新 `message` 文案，不新增结构化字段。放弃原因：下游很难稳定判断 401、限流、空数据这些不同故障。

### 3. 缓存写入采用“质量优先”规则

设计选择：

- 对同一 `target_a_trade_date`：
  - `ok` 可以覆盖 `partial/error`
  - `partial` 可以覆盖 `error`
  - `error` 不得覆盖已有 `ok/partial`
- 如果质量相同，优先保留 `captured_at` 更新且 `source_attempts` 更完整的记录。

理由：

- 当前线上最现实的故障是“上游突然拒绝访问”，这类失败如果覆盖当天已抓到的有效上下文，会直接降低历史回放质量。

备选方案：

- 始终以最新抓取覆盖缓存。放弃原因：会把偶发上游故障固化进缓存。

### 4. CLI 与 prompt 明确暴露 fallback 结果，但不引入新的主阶段

设计选择：

- `market-summary` 阶段 1 继续显示海外市场块，但状态文案应能区分：
  - 主源直接成功
  - 主源失败后 fallback 成功
  - 所有上游失败
- `AIProcessor` 在海外市场上下文缺口提示中引用结构化失败类型，例如“海外市场上下文缺失，主源被拒绝访问，勿臆测隔夜美股表现”。

理由：

- 用户要知道这是“市场没数据”还是“我们的上游被封了”。
- 模型也需要更具体的缺口约束，否则容易把没有抓到的数据当成常识补全。

## Risks / Trade-offs

- [引入多源后解析代码复杂度上升] → 将 provider 解析隔离为小函数，统一返回中间结构
- [免费 fallback 源字段语义不完全一致] → 只映射上一变更已约定的最小指标集，并在标准化层统一单位与时间字段
- [缓存保护可能保留较旧但成功的数据] → 只在同一目标交易日内启用质量优先，且保留 `captured_at` 供 CLI 判断时效
- [CLI 暴露过多诊断信息影响可读性] → 默认展示摘要，详细尝试序列留给日志或调试输出

## Migration Plan

1. 定义 provider 尝试结果结构和 `failure_type` 枚举。
2. 为海外市场上下文实现多源抓取与聚合标准化。
3. 调整缓存层的海外上下文 upsert 规则，加入质量优先保护。
4. 更新 CLI 与 AI prompt 的状态表达。
5. 补齐 401、fallback、缓存保护与回放测试。

回滚策略：

- 若 fallback provider 质量不稳定，可临时禁用该 provider，只保留结构化失败分类与缓存保护。
- 若新缓存规则出现兼容性问题，可先回退到旧写入策略，同时保留采集层多源逻辑独立验证。

## Open Questions

- 第一优先 fallback provider 选哪一个更合适：继续沿用现有依赖、接入新的免费 HTTP 源，还是从已有财经客户端中复用可用接口。
- `source_attempts` 是否需要完整落库，还是仅保留最终来源和最后一个失败摘要即可。
