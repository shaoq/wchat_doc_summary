## Why

当前 CLI 全部集中在单个 [src/cli.py](/Users/jie.hua/Documents/Developments/Projects/wchat_doc/src/cli.py) 文件中，命令声明、业务编排、展示逻辑和辅助函数混杂，文件规模已超过 1300 行。继续在现有结构上扩展功能会持续提高冲突率、理解成本和回归风险，因此需要先把 CLI 拆分为按领域组织的命令模块。

## What Changes

- 将现有单文件 CLI 拆分为按业务领域组织的命令模块，并保留统一入口。
- 分离命令注册、参数解析、终端展示和业务调用逻辑，减少共享文件上的编辑冲突。
- 保持现有命令名、子命令名和主入口调用方式不变，避免对用户形成破坏性变更。
- 为模块化 CLI 注册增加最小回归测试，确保帮助信息和主要命令面不回退。

## Capabilities

### New Capabilities
- `modular-cli-commands`: 提供按领域模块化组织并注册 CLI 命令的能力，同时保持统一入口和命令面稳定。

### Modified Capabilities

## Impact

- **Affected code**:
  - `src/cli.py`
  - 需要新增若干 CLI 模块文件
  - 可能少量影响命令相关服务导入路径
- **Affected tests**:
  - 需要增加 CLI 帮助与命令注册回归测试
- **Affected behaviors**:
  - `python -m src.cli --help`
  - `python -m src.cli ai --help`
  - 所有现有命令入口的注册方式
