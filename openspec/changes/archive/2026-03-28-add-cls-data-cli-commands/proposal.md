## Why

当前项目已经具备 CLS 电报和 CLS 看盘的数据抓取、入库与查询能力，但没有对应的 CLI 命令面。结果是这些能力只能被 `market-summary` 间接消费，用户无法主动抓取、刷新、查看本地 CLS 数据，也难以独立排障。

## What Changes

- 为 CLS 电报和 CLS 看盘增加独立 CLI 命令面。
- 支持用户显式触发 CLS 数据抓取 / 入库，而不是只能依赖市场总结链路。
- 支持查看本地已入库的 CLS 电报和看盘数据，便于验证和排障。
- 补 CLI 帮助与命令面回归测试。

## Capabilities

### New Capabilities
- `cls-data-cli-commands`: 提供独立的 CLI 命令来抓取、刷新和查看 CLS 电报与看盘数据。

### Modified Capabilities

## Impact

- **Affected code**:
  - `src/cli/main.py`
  - 需要新增 CLS 相关 CLI 模块
  - `src/services/cls_telegraph_service.py`
  - `src/services/cls_watch_service.py`
- **Affected tests**:
  - `tests/test_cli_commands.py`
  - 需要新增 CLS CLI 命令测试
- **Affected behaviors**:
  - 新增 CLS 数据抓取 / 查看命令
  - 用户可以独立验证本地 CLS 数据状态
