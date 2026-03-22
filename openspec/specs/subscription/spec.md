# Spec: 公众号订阅能力

## Capability Description

管理微信公众号的订阅关系，包括添加、删除、查询订阅。

## Interface

### 订阅服务 (SubscriptionService)

```python
class SubscriptionService:
    async def add_subscription(
        self,
        mp_id: str,
        name: str,
        intro: str = "",
        cover: str = ""
    ) -> Feed:
        """添加或激活订阅。

        如果公众号已存在但状态为停用，则激活；
        如果不存在，则创建新订阅。

        Args:
            mp_id: 公众号 ID (如 MP_WXS_xxx)
            name: 公众号名称
            intro: 简介
            cover: 头像 URL

        Returns:
            Feed 对象
        """

    async def remove_subscription(self, mp_id: str) -> bool:
        """取消订阅（软删除）。

        将 status 设为 0，不删除记录。

        Args:
            mp_id: 公众号 ID

        Returns:
            是否成功
        """

    async def list_subscriptions(
        self,
        active_only: bool = True
    ) -> list[Feed]:
        """获取订阅列表。

        Args:
            active_only: 是否只返回活跃订阅

        Returns:
            Feed 列表
        """

    async def get_subscription(self, mp_id: str) -> Feed | None:
        """获取单个订阅。

        Args:
            mp_id: 公众号 ID

        Returns:
            Feed 对象或 None
        """

    async def update_sync_time(self, mp_id: str) -> None:
        """更新最后同步时间。

        Args:
            mp_id: 公众号 ID
        """
```

## Data Model

```python
class Feed(Base):
    __tablename__ = "feeds"

    id: int              # 主键，自增
    mp_id: str           # 公众号 ID，唯一索引
    name: str            # 公众号名称
    intro: str           # 简介
    cover: str           # 头像 URL
    status: int          # 1=活跃, 0=停用
    sync_time: datetime  # 最后同步时间
    created_at: datetime # 创建时间
```

## CLI Commands

```bash
# 订阅公众号（通过文章 URL）
wchat subscribe https://mp.weixin.qq.com/s/xxx

# 取消订阅
wchat unsubscribe MP_WXS_xxx

# 查看订阅列表
wchat list

# 查看公众号详情
wchat info MP_WXS_xxx
```

## Usage Example

```python
from src.storage.database import get_db
from src.services.subscription import SubscriptionService

async def example():
    db = await get_db()
    service = SubscriptionService(db)

    # 添加订阅
    feed = await service.add_subscription(
        mp_id="MP_WXS_xxx",
        name="人民日报",
        intro="人民日报官方账号",
        cover="https://..."
    )

    # 查看订阅列表
    feeds = await service.list_subscriptions()
    for f in feeds:
        print(f.name, f.mp_id)

    # 取消订阅
    await service.remove_subscription("MP_WXS_xxx")
```

## Error Handling

| Error | Cause | Handling |
|-------|-------|----------|
| 订阅不存在 | mp_id 未找到 | 返回 None 或 False |
| 重复订阅 | mp_id 已存在 | 激活已有记录 |
| 数据库错误 | 连接失败 | 抛出异常，记录日志 |
