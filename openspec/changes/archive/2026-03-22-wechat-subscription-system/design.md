# Design: 微信公众号文章订阅系统

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                   │
│                         src/cli.py + scripts/                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                  │
│   │   login     │   │  subscribe  │   │   fetch     │   ...            │
│   └─────────────┘   └─────────────┘   └─────────────┘                  │
│                                                                         │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Service Layer                                 │
│                          src/services/                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐      │
│   │ AuthService     │   │ SubscriptionSvc │   │ FetcherService  │      │
│   │                 │   │                 │   │                 │      │
│   │ - start_login() │   │ - add_sub()     │   │ - fetch_feed()  │      │
│   │ - check_login() │   │ - remove_sub()  │   │ - fetch_all()   │      │
│   │ - get_token()   │   │ - list_subs()   │   │ - incremental() │      │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘      │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                     AIProcessor                                  │  │
│   │  - summarize() - extract_keywords() - classify() - sentiment()  │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                   │
│                           src/api/                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────┐   ┌─────────────────────────────┐    │
│   │      WeReadClient           │   │      Article API            │    │
│   │                             │   │                             │    │
│   │ - get_login_qrcode()        │   │ - fetch_article_content()   │    │
│   │ - get_login_result()        │   │ - parse_article_html()      │    │
│   │ - get_mp_info(url)          │   │ - extract_images()          │    │
│   │ - get_articles(mp_id, page) │   │                             │    │
│   └─────────────────────────────┘   └─────────────────────────────┘    │
│                                                                         │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Storage Layer                                  │
│                        src/storage/ + src/models/                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    SQLite + SQLAlchemy                           │  │
│   │                                                                  │  │
│   │   ┌─────────┐    ┌──────────┐    ┌─────────┐                   │  │
│   │   │  Feed   │    │ Article  │    │  Auth   │                   │  │
│   │   │         │    │          │    │         │                   │  │
│   │   │ - mp_id │    │ - title  │    │ - token │                   │  │
│   │   │ - name  │    │ - content│    │ - status│                   │  │
│   │   │ - status│    │ - summary│    │         │                   │  │
│   │   └─────────┘    └──────────┘    └─────────┘                   │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### Feed (公众号订阅)

```python
class Feed:
    id: int              # 主键
    mp_id: str           # 公众号 ID (如: MP_WXS_xxx)，唯一
    name: str            # 公众号名称
    intro: str           # 简介
    cover: str           # 头像 URL
    status: int          # 状态: 1=订阅, 0=未订阅
    sync_time: datetime  # 最后同步时间
    created_at: datetime # 创建时间
```

### Article (文章)

```python
class Article:
    id: int              # 主键
    feed_id: int         # 关联 Feed
    article_id: str      # 文章 ID，唯一
    title: str           # 标题
    content: str         # 正文 HTML
    summary: str         # AI 摘要 (可选)
    pic_url: str         # 封面图
    original_url: str    # 原文链接
    publish_time: datetime
    created_at: datetime
```

### Auth (认证信息)

```python
class Auth:
    id: int              # 主键
    token: str           # 微信读书 Token
    username: str        # 用户名
    status: int          # 状态: 1=有效, 0=失效
    created_at: datetime
```

## API Design

### 微信读书代理 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/login/platform` | GET | 获取登录二维码 |
| `/api/v2/login/platform/{id}` | GET | 获取登录结果 (Token) |
| `/api/v2/platform/wxs2mp` | POST | 通过文章链接获取公众号信息 |
| `/api/v2/platform/mps/{mpId}/articles` | GET | 获取公众号文章列表 |

### 文章内容获取

直接请求：`https://mp.weixin.qq.com/s/{articleId}`

## CLI Commands

```bash
wchat init                      # 初始化数据库
wchat login                     # 登录微信读书
wchat logout                    # 登出
wchat subscribe <URL>           # 订阅公众号
wchat unsubscribe <mp_id>       # 取消订阅
wchat fetch [--all] [mp_id]     # 抓取文章
wchat list                      # 查看订阅列表
wchat info <mp_id>              # 查看公众号详情
wchat article <article_id>      # 查看文章详情
wchat export [--format] [-o]    # 导出文章

# AI 子命令
wchat ai summarize <id>         # 生成摘要
wchat ai keywords <id>          # 提取关键词
wchat ai classify <id>          # 智能分类
wchat ai sentiment <id>         # 情感分析
wchat ai batch-summarize        # 批量处理
```

## Error Handling

1. **Token 过期**: 提示用户重新登录
2. **API 限流 (429)**: 自动重试，延迟控制
3. **文章抓取失败**: 记录日志，跳过继续
4. **网络错误**: 重试机制 (max_retries)

## Security Considerations

- Token 存储在本地 SQLite 数据库
- API Key 通过环境变量配置
- 不在日志中输出敏感信息
