# Spec: 文章抓取能力

## Capability Description

从微信公众号抓取文章列表和内容，支持全量抓取和增量更新。

## Interface

### 抓取服务 (FetcherService)

```python
class FetcherService:
    async def fetch_feed(
        self,
        mp_id: str,
        max_pages: int = 5
    ) -> list[Article]:
        """抓取指定公众号的文章。

        Args:
            mp_id: 公众号 ID
            max_pages: 最大抓取页数

        Returns:
            抓取到的文章列表
        """

    async def fetch_all(self) -> dict[str, list[Article]]:
        """抓取所有已订阅公众号的文章。

        Returns:
            字典，key 为 mp_id，value 为文章列表
        """

    async def fetch_incremental(
        self,
        mp_id: str
    ) -> list[Article]:
        """增量抓取（只获取新文章）。

        检查数据库中已有的最新文章时间，只获取更新的文章。

        Args:
            mp_id: 公众号 ID

        Returns:
            新抓取的文章列表
        """

    async def get_mp_info_from_article(
        self,
        article_url: str
    ) -> dict[str, Any]:
        """从文章链接获取公众号信息。

        Args:
            article_url: 微信公众号文章链接

        Returns:
            包含 mp_id, name, intro, cover 的字典
        """
```

### 文章 API

```python
async def fetch_article_content(article_id: str) -> str:
    """抓取文章 HTML 内容。

    请求 https://mp.weixin.qq.com/s/{article_id}

    Args:
        article_id: 文章 ID

    Returns:
        HTML 字符串
    """

def parse_article_html(html: str) -> dict[str, Any]:
    """解析微信公众号文章 HTML。

    Args:
        html: 文章 HTML

    Returns:
        包含 title, content, publish_time, author, cover 的字典
    """

def extract_images(html: str) -> list[str]:
    """提取文章中的图片 URL。

    Args:
        html: 文章 HTML

    Returns:
        图片 URL 列表
    """
```

## Data Model

```python
class Article(Base):
    __tablename__ = "articles"

    id: int              # 主键，自增
    feed_id: int         # 关联 Feed，外键
    article_id: str      # 文章 ID，唯一索引
    title: str           # 标题
    content: str         # 正文 HTML
    summary: str         # AI 摘要（可选）
    pic_url: str         # 封面图
    original_url: str    # 原文链接
    publish_time: datetime
    created_at: datetime
```

## CLI Commands

```bash
# 抓取所有订阅
wchat fetch --all

# 抓取指定公众号
wchat fetch MP_WXS_xxx

# 查看文章详情
wchat article 1

# 导出文章
wchat export --format json -o articles.json
```

## Usage Example

```python
from src.storage.database import get_db
from src.api.weread import WeReadClient
from src.services.fetcher import FetcherService
from src.services.subscription import SubscriptionService

async def example():
    db = await get_db()
    client = WeReadClient(token="xxx")
    subscription_service = SubscriptionService(db)
    fetcher = FetcherService(client, db, subscription_service)

    # 从文章 URL 获取公众号信息
    mp_info = await fetcher.get_mp_info_from_article(
        "https://mp.weixin.qq.com/s/abc123"
    )
    print(mp_info["name"])  # 公众号名称

    # 抓取指定公众号
    articles = await fetcher.fetch_feed("MP_WXS_xxx")
    for article in articles:
        print(article.title)

    # 抓取所有订阅
    results = await fetcher.fetch_all()
    for mp_id, articles in results.items():
        print(f"{mp_id}: {len(articles)} 篇")
```

## Error Handling

| Error | Cause | Handling |
|-------|-------|----------|
| Token 过期 | 登录失效 | 提示重新登录 |
| API 限流 (429) | 请求过快 | 自动重试，延迟控制 |
| 文章不存在 | article_id 无效 | 跳过，记录日志 |
| 网络错误 | 连接失败 | 重试机制 |
