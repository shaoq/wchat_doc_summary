## Context

当前 `_fetch_and_save_article` 方法在保存文章时，`publish_time` 只从 HTML 解析结果 (`parsed.get("publish_time")`) 获取。但微信公众号文章 HTML 已不再暴露发布时间元素，导致所有文章的 `publish_time` 为 NULL。

微信读书 API 的 `get_articles` 响应可能包含 `publish_time` 字段（已在 `fetch_incremental` 中使用），应优先使用。

## Goals / Non-Goals

**Goals:**
- 修复发布时间保存逻辑
- 优先使用 API 响应中的 `publish_time`
- 保留 HTML 解析作为后备

**Non-Goals:**
- 不修复已有文章数据（需重新抓取）
- 不修改 API 客户端

## Decisions

### 1. 发布时间来源优先级
- **决定**: API 响应 > HTML 解析 > NULL
- **理由**: API 数据更可靠，HTML 解析作为兼容后备

### 2. 时间格式解析
- **决定**: 复用现有的 `_parse_publish_time` 逻辑
- **理由**: 已支持多种格式，无需新增

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| API 返回的时间格式与预期不同 | 复用现有解析逻辑，增加日志 |
| 已有数据无法修复 | 用户可删除订阅重新抓取 |
