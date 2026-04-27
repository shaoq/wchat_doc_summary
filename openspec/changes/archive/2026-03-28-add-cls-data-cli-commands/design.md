## Context

CLS 电报和看盘的底层能力已经存在，但它们目前属于“内部依赖”而不是“显式产品能力”。这会产生两个现实问题：

- 用户无法在市场总结之外主动准备 CLS 数据
- 当 `market-summary` 的 CLS 数据为空时，用户无法独立检查是抓取、入库还是聚合出了问题

CLI 需要把这类内部能力提升成可独立执行的用户面。

## Goals / Non-Goals

**Goals:**
- 为 CLS 电报和看盘提供独立、可发现的命令入口。
- 支持抓取 / 入库和查看两类基本操作。
- 保持和现有服务层契约一致，不在 CLI 层重新实现抓取逻辑。

**Non-Goals:**
- 不在本次变更中重构 CLS API client。
- 不改变 `market-summary` 对 CLS 数据的消费方式。
- 不要求一次性提供完整管理后台，只提供最小可用命令面。

## Decisions

### 1. 通过独立命令组暴露 CLS 能力

CLI 应提供专门的 CLS 命令组，而不是把相关操作塞进 `market-summary` 或 `system` 命令下。

这样用户可以直接表达：
- 抓取 CLS 电报
- 抓取 CLS 看盘
- 查看本地 CLS 数据

### 2. CLI 只负责参数和展示，抓取 / 入库仍走 service

命令层不直接操作数据库或远端 API 细节，而是复用现有 `CLSTelegraphService` / `CLSWatchService`。

### 3. 最小命令面包含“抓取”和“查看”

如果只有抓取没有查看，用户仍无法排障；如果只有查看没有抓取，用户也无法主动刷新数据。因此最小集应至少覆盖：
- 抓取 / 入库
- 列表查看

## Risks / Trade-offs

- [命令面增加会让 CLI 变大] → 用独立命令组控制复杂度。
- [CLS 数据量可能较大] → 查看命令默认分页或限制条数。

## Migration Plan

1. 设计 CLS 命令组与最小子命令。
2. 接入现有 service 层抓取 / 查询能力。
3. 补命令帮助与最小执行测试。

## Open Questions

- CLS 命令应为顶层 `wchat cls ...`，还是挂在 `wchat market-data ...` 下；两者都可行，但顶层更直观。
