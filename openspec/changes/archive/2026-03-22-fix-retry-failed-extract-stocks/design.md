## Context

`AIProcessor._get_processed_articles` 方法当前只根据 `task_type` 查询已处理的文章，不考虑处理状态。这导致失败的文章也会被跳过。

**当前代码**:
```python
result = await session.execute(
    select(ArticleProcessing.article_id).where(
        ArticleProcessing.article_id.in_(article_ids),
        ArticleProcessing.task_type == task_type,
    )
)
```

## Goals / Non-Goals

**Goals:**
- 只跳过处理成功的文章 (`status='success'`)
- 允许失败的文章 (`status='failed'`) 被重新处理

**Non-Goals:**
- 不改变其他 AI 处理任务的行为（但该方法是通用的，修改会应用到所有任务）

## Decisions

### 在查询中添加 status 过滤

**选择**: 添加 `ArticleProcessing.status == 'success'` 条件

**理由**: 简单直接，只修改一处代码，影响所有使用该方法的任务类型。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 修改会影响所有 AI 任务类型 | 这是期望行为，所有任务都应支持失败重试 |
