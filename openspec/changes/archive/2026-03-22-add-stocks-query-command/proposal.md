## Why

当前 `extract-stocks` 命令只能提取股票信息并保存到文件和数据库，但缺乏查询能力。用户需要直接通过 CLI 查询已提取的股票信息，包括查看所有股票、搜索特定股票、查看股票出现的文章等。

## What Changes

- 新增 `wchat ai stocks` 命令组，提供股票查询能力
- 支持子命令：
  - `wchat ai stocks list` - 列出所有提取的股票及出现次数
  - `wchat ai stocks search <关键词>` - 搜索包含关键词的股票
  - `wchat ai stocks show <股票名>` - 显示某股票出现在哪些文章中

## Capabilities

### New Capabilities

- `stocks-query`: 股票信息查询能力

### Modified Capabilities

无

## Impact

- **新增代码**: `src/cli.py` 中新增 `stocks` 命令组
- **数据来源**: 查询 `article_processing` 表中 `task_type='extract_stocks'` 的记录
