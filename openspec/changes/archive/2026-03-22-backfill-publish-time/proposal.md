## Why

已存在的文章 `publish_time` 为空，需要补全。fetch 完成后批量更新这些文章的发布时间。

## What Changes

- 在 `FetcherService` 添加 `backfill_publish_time` 方法
- fetch 完成后自动调用此方法
- 支持手动触发：`wchat backfill <mp_id>`

## Capabilities

### New Capabilities

- `backfill-publish-time`: 批量更新文章发布时间

### Modified Capabilities

无

## Impact

- **代码**: `src/services/fetcher.py` - 新增方法
- **CLI**: `src/cli.py` - 新增命令
- **数据**: 填充 publish_time 为空的记录
