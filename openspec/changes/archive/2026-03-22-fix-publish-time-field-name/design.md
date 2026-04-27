## Context

微信读书 API 返回的文章数据使用驼峰命名 `publishTime`，但代码使用下划线 `publish_time` 获取。

## Goals / Non-Goals

**Goals:**
- 兼容两种命名风格的字段
- 正确保存发布时间

**Non-Goals:**
- 不修复已有数据（用户需重新抓取）

## Decisions

### 同时检查两种字段名
- **决定**: `article_info.get("publishTime") or article_info.get("publish_time")`
- **理由**: 确保兼容性，即使 API 改变字段名也能工作

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 已有数据无法修复 | 用户可删除订阅重新抓取 |
