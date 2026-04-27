## Why

当前仓库存在一些低风险但持续制造噪音的问题，例如配置字段重复定义、README 明显落后于真实功能、以及 `.bak` 与 `__pycache__` 这类不应作为长期代码上下文存在的文件。这些问题不会立刻阻塞功能，但会不断提高理解成本和维护摩擦，因此适合单独做一次工程卫生清理。

## What Changes

- 清理配置层中的重复字段定义与明显的命名噪音。
- 更新 README，使其反映当前真实命令面和主要功能。
- 清理不应作为源码长期保留的备份文件和缓存产物，并补充相应仓库忽略策略。
- 审视项目根目录中对后续维护者有误导性的陈旧说明，降低认知成本。

## Capabilities

### New Capabilities
- `project-hygiene`: 为配置、文档和仓库清洁度提供持续可维护的工程卫生规范。

### Modified Capabilities

## Impact

- **Affected code**:
  - `config/settings.py`
  - `README.md`
  - 可能影响仓库忽略配置文件
- **Affected repository artifacts**:
  - `.bak` 文件
  - `__pycache__` 产物
  - 说明性文档内容
