## Context

当前 `src/cli.py` 第 310 行定义了一个 Click 命令 `def list(...)`，该函数名覆盖了 Python 内置的 `list()` 函数。当其他命令（如 `extract_stocks`）使用 `list()` 转换迭代器时，实际调用的是 Click 命令对象，触发参数解析并导致错误。

## Goals / Non-Goals

**Goals:**
- 将 `list` 命令重命名为 `ls`，避免与 Python 内置函数冲突
- 保持命令功能不变

**Non-Goals:**
- 不改变命令的参数或行为
- 不添加新功能

## Decisions

### 命令名称选择: `ls`

**选择**: `ls`
**备选方案**:
- `list` - 当前名称，与 Python 冲突
- `subs` - 订阅缩写，但语义不够直观
- `list-subscriptions` - 明确但过长

**理由**: `ls` 是类 Unix 系统中常用的列表命令，用户熟悉度高，且不会与 Python 内置函数冲突。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 破坏性变更，用户习惯需调整 | 在 README 和帮助信息中提示新命令名 |
