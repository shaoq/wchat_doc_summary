# Tasks

## 任务 1： 在 SubscriptionService 中新增 `list_subscriptions_with_stats()` 方法

- [x] 在 `SubscriptionService` 中新增 `list_subscriptions_with_stats()` 方法

- 方法签名：
  ```python
  async def list_subscriptions_with_stats(
      self,
 active_only: bool = True,
  ) -> list[tuple[Feed, int, datetime | None]
  """
  async with self.db.get_session() as session:
      # 使用 LEFT JOIN + GROUP by 一次查询获取所有订阅的统计信息
      query = (
          select(
              Feed,
              func.count(Article.id).label("article_count")
              func.max(Article.publish_time).label("latest_article_time")
          )
          .outerjoin(Article, Article.feed_id == Feed.id)
          .group_by(Feed.id)
          .order_by(Feed.created_at.desc())
      )

      if active_only:
          query = query.where(Feed.status == 1)

      result = await session.execute(query)
      rows = result.all()

      # 转换为元组列表 (Feed, article_count, latest_article_time)
      feeds_with_stats = []
      for row in rows:
          feed = row[0]
          article_count = row[1]
          latest_article_time = row[2]
          feeds_with_stats.append((feed, article_count, latest_article_time))

      logger.info(f"获取订阅列表（带统计）: {len(feeds_with_stats)} 条记录")
      return feeds_with_stats
