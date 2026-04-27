## Context

当前测试体系有两个明显问题：

- 关键服务大量依赖 `MagicMock`/`AsyncMock` 模拟数据库会话，导致 `session.add()`、`session.merge()`、`result.scalars().all()` 等行为与真实 SQLAlchemy 异步会话不一致
- 测试运行中已经出现 `aiosqlite` 线程在事件循环关闭后回调的 warning，说明 fixture 与事件循环清理方式也需要治理

这使得当前测试更多是在验证“mock 是否按预期配置”，而不是验证系统真实行为。后续多个 change 都会重构 service 层，如果没有更可靠的集成测试，回归风险会不断增大。

## Goals / Non-Goals

**Goals:**
- 建立可复用的 SQLite 异步集成测试基础设施
- 为关键 service 增加真实 session 路径测试
- 降低伪造 AsyncSession 行为带来的误报和漏报
- 改善 pytest 事件循环与异步资源清理方式

**Non-Goals:**
- 不要求所有现有测试都重写为集成测试
- 不引入外部数据库服务，继续使用 SQLite
- 不在本次变更中修复所有业务 bug，只提升测试可信度

## Decisions

### 1. 采用“单元测试保留，关键路径增加集成测试”的双层策略

不会全盘放弃 mock 测试，而是保留纯逻辑类单元测试；对事务、ORM、会话生命周期敏感的 service 则增加 SQLite 异步集成测试。

备选方案：
- 全量改成集成测试。放弃原因：成本高、运行时间长，且并非所有逻辑都需要真实数据库。

### 2. 为测试提供可复用的临时数据库 fixture，而不是广泛复用 in-memory mock

集成测试将使用临时 SQLite 数据库和真实 `Database` / `AsyncSession` 路径，确保表创建、事务提交和查询结果与生产路径一致。

备选方案：
- 继续使用 `sqlite+aiosqlite:///:memory:` 并大量 mock 上层。放弃原因：核心问题正是上层行为失真。

### 3. 事件循环与异步资源由 fixture 显式管理

测试基础设施需要显式管理：

- event loop 生命周期
- engine dispose
- session close
- 临时数据库销毁

以减少 `Event loop is closed` 和后台线程残留告警。

## Risks / Trade-offs

- [集成测试增加运行时间] → 只覆盖关键 service 路径，不替代全部单元测试
- [测试夹具重构会波及较多测试文件] → 分阶段迁移，先从当前失败和 warning 最集中的文件开始
- [部分现有测试会因更真实的行为而暴露新问题] → 视为收益而非回归，优先修正错误假设

## Migration Plan

1. 重构 `tests/conftest.py` 中的异步数据库与事件循环 fixture
2. 为缓存服务、认证服务、订阅服务增加真实 session 路径测试
3. 将当前最失真的 mock 测试逐步替换为集成测试
4. 跑全量 pytest 并清理主要 warning

回滚策略：
- 若新 fixture 大范围破坏现有测试，可保留新集成测试文件，暂时回退共享 fixture 迁移

## Open Questions

- 是否需要把集成测试单独分目录，例如 `tests/integration/`
- 哪些现有服务测试最适合优先迁移：缓存服务、认证服务、还是订阅服务
