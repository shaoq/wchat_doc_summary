## Why

当前 `extract-stocks` 命令只输出详细格式的股票报告（包含每篇文章的股票信息），用户需要一个更简洁的股票列表格式，便于快速查看和复制。简化格式只包含股票名称和代码，按每 10 个一组分组显示。

## What Changes

- 添加 `--simple-info` 参数（flag，默认 False）
- 当指定 `--simple-info` 时，额外输出简化格式的股票列表文件
- 输出文件名：`{mp_id}_stocks_{yymmdd}_info.txt`
- 格式：每 10 个股票一组，用逗号分隔，格式为 `股票名(代码)`

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

- `extract-stocks`: 添加 `--simple-info` 参数支持简化格式输出

## Impact

- **受影响代码**: `src/cli.py` 中的 `extract_stocks` 命令
- **输出文件**: 新增 `{mp_id}_stocks_{yymmdd}_info.txt` 文件
