## Why

当前测试体系虽然数量不少，但关键 service 的验证高度依赖 `MagicMock` 和 `AsyncMock`，已经出现“测试通过路径”和“真实数据库/事件循环路径”分叉的问题。现有失败与 warning 说明，仅靠单元 mock 已不足以支撑后续重构，因此需要补一层面向真实 async session 与 SQLite 的服务级集成测试。

## What Changes

- 为关键 service 引入更贴近真实运行环境的 SQLite 异步集成测试基础设施。
- 减少对伪造 `AsyncSession` 行为的深度 mock，优先验证真实事务、会话和 ORM 交互。
- 为认证、订阅、抓取、市场缓存等关键服务补充最小闭环集成测试。
- 调整 pytest fixtures 与事件循环管理，减少事件循环关闭和后台线程残留告警。
- 将现有易失真的测试改写为“单元测试 + 集成测试”分层结构。

## Capabilities

### New Capabilities
- `service-integration-tests`: 为核心服务提供基于真实 SQLite 异步会话的集成测试能力。

### Modified Capabilities

## Impact

- **Affected code**:
  - `tests/conftest.py`
  - `tests/test_services.py`
  - `tests/test_market_data_cache_service.py`
  - 可能新增多个 service 级集成测试文件
- **Affected systems**:
  - pytest fixture 结构
  - 测试数据库创建与销毁方式
  - 事件循环管理方式
