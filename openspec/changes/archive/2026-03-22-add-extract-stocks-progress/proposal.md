## Why

`extract-stocks` 命令处理大量文章时，用户无法直观了解处理进度。当前只显示每篇文章完成后的信息，缺少进度条和实时状态统计，用户体验不佳。

## What Changes

- 添加 Rich Progress 进度条，显示处理进度（第 N/M 篇）
- 实时显示当前处理的文章标题
- 显示成功/跳过/失败的计数

## Capabilities

### New Capabilities

- `progress-display`: 批量任务进度显示能力

### Modified Capabilities

- `extract-stocks`: 添加进度条显示

## Impact

- **受影响代码**: `src/cli.py` 中的 `extract_stocks` 命令
- **依赖**: Rich 库（已在项目中使用）
