## Why

CLI 中的 `list` 命令与 Python 内置函数 `list()` 同名，导致在其他命令中使用 `list()` 时会错误地调用 Click 命令对象而非 Python 内置函数。这引发了 `TypeError: object of type 'Article' has no len()` 错误，因为 Click 在解析参数时对 Article 对象调用了 `len()`。

## What Changes

- **BREAKING**: 将 `wchat list` 命令重命名为 `wchat ls`
- 更新相关帮助文档和命令说明

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

无需求变更，仅为命令重命名（实现细节变更）。

## Impact

- **受影响代码**: `src/cli.py` 中的 `list` 命令定义（第 308-348 行）
- **用户影响**: 用户需要将 `wchat list` 改为 `wchat ls`
- **向后兼容**: 此为破坏性变更，旧命令 `wchat list` 将不再可用
