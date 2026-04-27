# Design: enhance `wchat list` command

<!-- Context -->
现有 `wchat list` 崽令显示订阅列表，包括：ID、公众号名称、公众号 ID、状态、最后同步时间和。
新增两列:
- 文章数量: 显示该公众号下已抓取的文章总数
- 最近文章: 显示最新一篇文章的发布时间

## 技术方案

使用 SQL 聚合查询，单次获取所有订阅的文章数量和最新文章时间，避免 N+1 查询问题。

```python
async def list_subscriptions_with_stats(self, active_only: bool = True) -> list[tuple[Feed, int, datetime | None]:
    """获取订阅列表及统计数据。

    使用单个 SQL 聚合查询，避免 N+1 查询问题。

    Args:
        active_only: 是否只返回活跃的订阅

    Returns:
        订阅列表，每个元素为 (Feed, 文章数量, 最新文章时间)
    """
    async with self.db.get_session() as session:
        # 使用 LEFT JOIN + GROUP BY 获取所有订阅及其统计数据
        query = (
            select(
                Feed,
                func.count(Article.id).label('article_count'),
                func.max(Article.publish_time).label('latest_article_time'),
            )
            if active_only:
                query = query.where(Feed.status == 1)
            query = query.group_by(Feed.id).order_by(Feed.created_at.desc())

        result = await session.execute(query)
        feeds = result.scalars().all()
        stats = []
        for feed in feeds:
            stats.append({
                "feed_id": feed.id,
                "article_count": row.article_count,
                "latest_article_time": row.latest_article_time,
            })
        return feeds, stats
```
        return feeds, stats
```
