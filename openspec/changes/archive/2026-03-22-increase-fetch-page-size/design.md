## Context

当前文章抓取流程：

```
CLI/RUN.py → FetcherService.fetch_feed() → WeReadClient.get_articles() → 微信读书 API
                    │                              │
              max_pages=5                    page=1,2,3... (无 page_size)
                    │                              │
                    └──────────────────────────────┘
                          API 默认 pageSize=10
                          最大文章数 = 5 × 10 = 50
```

**约束**：
- 微信读书代理 API 支持 `pageSize` 参数（待验证上限）
- 需保持向后兼容性，新参数必须有默认值

## Goals / Non-Goals

**Goals:**
- 增加 `page_size` 参数支持，默认值 50
- 抓取上限从 50 篇提升到 250 篇（5 页 × 50 篇）
- 保持向后兼容，不破坏现有调用

**Non-Goals:**
- 不修改 `max_pages` 的默认值（保持 5）
- 不修改 CLI 命令参数（保持内部实现变更）
- 不处理 API 返回异常或分页逻辑变更

## Decisions

### 1. 参数传递方式

**选择**: 配置文件 + 参数透传

```
Settings.fetch_page_size (默认 50)
        ↓
FetcherService.fetch_feed(page_size=settings.fetch_page_size)
        ↓
WeReadClient.get_articles(page_size=page_size)
```

**理由**:
- 配置文件允许用户全局调整
- 参数透传允许特定调用覆盖
- 符合现有代码模式（如 `max_retries`、`request_timeout`）

**备选方案**:
- 硬编码常量 → 不够灵活
- 仅配置文件 → 无法针对特定调用调整

### 2. API 参数命名

**选择**: `pageSize`（驼峰）

**理由**: 遵循微信读书代理 API 的命名约定（从 `page` 参数推断）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| API 可能不支持大 `pageSize` | 默认值 50 是合理假设；若失败会抛出异常，不会静默丢失数据 |
| 大页面可能导致响应延迟 | 已有 `request_timeout` 和 `max_retries` 机制 |
| 部分公众号文章较少 | 分页逻辑已有 `len(article_list) < page_size` 提前终止 |
