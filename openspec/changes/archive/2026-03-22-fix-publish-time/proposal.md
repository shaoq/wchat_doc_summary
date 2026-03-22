## Why

抓取的文章 `publish_time` 全部为空，导致 `show` 命令显示"未知"发布时间，且无法按实际发布时间排序。

根因：`_fetch_and_save_article` 方法只从 HTML 解析发布时间（微信文章已不暴露此字段），未使用微信读书 API 响应中可能存在的 `publish_time`。

## What Changes

- 修改 `_fetch_and_save_article` 方法，优先从 API 响应 `article_info` 获取 `publish_time`
- 保留 HTML 解析作为后备方案

## Capabilities

### New Capabilities

无（这是 bug 修复，不引入新能力）

### Modified Capabilities

- `article-fetch`: 文章抓取时正确保存发布时间

## Impact

- **代码**: `src/services/fetcher.py` - `_fetch_and_save_article` 方法
- **数据**: 新抓取的文章将正确保存发布时间
- **向后兼容**: 已有文章需要重新抓取才能获取发布时间
