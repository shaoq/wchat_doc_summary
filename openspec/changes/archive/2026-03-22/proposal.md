# Proposal: Enhance list command with article count and latest article time

## Problem Statement

当前 `wchat list` 匽令显示：
- ID
- 公众号名称
- 公众号 ID
- 状态
- 最后同步

用户希望新增两列：
- **文章数量** - 当前公众号下的文章总数
- **最近文章时间** - 该公众号最新一篇文章的发布时间

## 目标用户

希望查看订阅列表时能快速了解：
1. 每个公众号有多少文章
2. 每个公众号最近更新是什么时候

## 涉及模块
- `src/cli.py` - CLI 入口
- `src/services/subscription.py` - 订阅服务

- `src/models/schema.py` - 数据模型

## 技术方案
使用 SQL 聚合查询 (LEFT JOIN + GROUP BY) 一次性获取所有数据：

```python
from sqlalchemy import func, select

async with db.get_session() as session:
    query = (
        select(
            Feed,
            func.count(Article.id).label('article_count'),
            func.max(Article.publish_time).label('latest_article_time')
        )
        .outerjoin(Article, Article.feed_id == Feed.id)
        .group_by(Feed.id)
    )
    if active_only:
        query = query.where(Feed.status == 1)

    query = query.order_by(Feed.created_at.desc())

    result = await session.execute(query)
    return list[tuple]
```

