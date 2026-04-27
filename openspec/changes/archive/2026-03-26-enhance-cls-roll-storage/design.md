## Context

基于已实现的 `enhance-cls-roll-api` 变更，当前 `wchat cls-roll list` 命令只能实时获取数据并显示。用户需要将抓取的电报数据持久化保存到数据库，以便后续查询和分析。

## Goals / Non-Goals

**Goals:**
- 将 `cls-roll list` 重命名为 `cls-roll fetch`，抓取数据并保存到数据库
- 新增 `cls-roll ls` 命令查看已保存的电报
- 支持 `--category` 参数（默认 red）
- 基于 `telegraph_id` 去重

**Non-Goals:**
- 不实现其他 category 类型的完整支持（仅预留字段）
- 不实现电报内容的 AI 处理

## Decisions

### 1. 数据表设计

**决定**: 新建独立表 `cls_telegraphs`

```sql
CREATE TABLE cls_telegraphs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegraph_id VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL,
    content TEXT,
    ctime INTEGER NOT NULL,
    level INTEGER DEFAULT 1,
    category VARCHAR(32) DEFAULT 'red',
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**理由**:
- 电报数据与公众号文章数据结构不同，独立表更清晰
- `telegraph_id` 作为唯一标识，支持去重
- `category` 字段预留扩展

### 2. CLI 命令重构

**决定**:
- `fetch`: 抓取并保存，只输出统计信息
- `ls`: 查询已保存数据，支持格式化输出

**理由**:
- 语义清晰：fetch = 获取并存储，ls = 查看
- 与现有 `wchat fetch` / `wchat ls` 命令风格一致

### 3. 去重策略

**决定**: 跳过已存在（INSERT OR IGNORE）

**理由**:
- 电报内容不变，无需更新
- 简化逻辑，避免复杂判断

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 数据量增长 | 添加时间索引，支持按时间范围查询 |
| API 变更 | `telegraph_id` 作为唯一标识，即使字段变化也能去重 |
