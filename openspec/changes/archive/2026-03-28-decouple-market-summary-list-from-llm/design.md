## Context

`market-summary` 命令同时承载了“查看历史总结”和“生成新总结”两类操作，但当前 CLI 在进入分支判断前就初始化了 `AIProcessor`。由于 `AIProcessor` 构造阶段会立即校验 LLM API Key，纯本地只读的 `--list` 分支也会被远端配置阻塞。

## Goals / Non-Goals

**Goals:**
- 让 `--list` 在没有 LLM 配置时仍然可用。
- 让 `market-summary` 各分支按需初始化依赖。
- 用测试锁住无 LLM 配置下的列表行为。

**Non-Goals:**
- 不调整市场总结的 AI 生成逻辑。
- 不修改 LLM 配置模型本身。

## Decisions

### 1. 按分支延迟初始化 `AIProcessor`

只有在真正进入 AI 生成阶段时，CLI 才应创建 `AIProcessor`。`--list` 分支只需要数据库和 `MarketAnalyzer`。

### 2. 依赖初始化顺序服从命令语义

列表、只读、纯本地操作不应初始化需要远端配置的对象。这个原则后续也可推广到其它 CLI 命令。

## Risks / Trade-offs

- [延迟初始化会让 CLI 结构多一层分支] → 这是必要的按需依赖管理成本。

## Migration Plan

1. 调整 `market-summary` 命令的依赖初始化顺序。
2. 为无 LLM 配置场景补测试。

## Open Questions

- 是否要顺手审查其它 CLI 命令是否也存在类似的“过早初始化重依赖”问题。
