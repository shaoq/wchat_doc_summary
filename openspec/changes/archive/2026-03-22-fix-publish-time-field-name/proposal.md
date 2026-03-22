## Why

发布时间字段保存失败。微信读书 API 返回 `publishTime`（驼峰命名），但代码使用 `publish_time`（下划线命名）获取。

## What Changes

- 修改 `_parse_publish_time` 辅助函数，增加 `publishTime` 作为备选字段名
- 修改 `_fetch_and_save_article` 方法，同时检查两种字段名

## Capabilities

### New Capabilities

无

### Modified Capabilities

- `article-fetch`: 修复发布时间字段名解析

## Impact

- **代码**: `src/services/fetcher.py` - 辅助函数和调用方
- **数据**: 新抓取的文章将正确保存发布时间
