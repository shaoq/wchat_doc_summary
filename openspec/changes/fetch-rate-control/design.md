## Context

当前 `fetch --all` 仅在订阅切换时有 3~5s 等待，订阅内部的列表翻页、文章内容抓取、backfill 全部无间隔。实际上只有一层控制，导致在单订阅内部产生突发式密集请求，频繁触发微信读书 API 限流 (RateLimitError)。

已有的 `rate-limit-circuit-breaker` 只处理**被动**限流后的熔断，缺少**主动**限速机制。

三个请求层级访问不同域名：
- **L1 列表页**: WeRead API — 有 RateLimitError 检测
- **L2 文章内容**: mp.weixin.qq.com — 无限流检测，直接封 IP
- **L3 回填**: 复用 L1 列表 API

## Goals / Non-Goals

**Goals:**
- 每个外部 HTTP 请求后都有可配置的等待间隔
- 全局滑动窗口兜底，硬性限制总请求密度
- 回调式进度通知，让用户实时看到抓取状态和等待倒计时
- 所有间隔参数通过 settings 可配置

**Non-Goals:**
- 不做域名级独立限速（L1/L2 共享同一全局窗口，简化实现）
- 不做等待期间的精确秒级倒计时（只显示"等待 Ns"静态文本即可）
- 不改变已有的限流熔断逻辑（rate-limit-circuit-breaker 保持不变）

## Decisions

### D1: 滑动窗口速率限制器

**选择**: 内存滑动窗口（记录最近 N 秒的请求时间戳）

**替代方案**: 令牌桶 — 更复杂，适合需要突发的场景，此处不需要

**实现**: `RateLimiter` 类，`async acquire()` 方法。维护请求时间戳列表，`acquire()` 时清理过期时间戳、检查窗口内数量、必要时 sleep。

### D2: 间隔插入位置

**选择**: 在 fetcher 层的循环中直接调用，而非在 httpx 中间件层

**理由**: 间隔语义是业务级的（"每翻一页" / "每抓一篇文章"），而非每个 HTTP 请求。中间件层无法区分列表请求和文章请求，也无法跳过"已存在"的文章。

### D3: 回调式进度通知

**选择**: fetcher 方法接受 `Callable[[FetchProgressEvent], None] | None` 回调

**替代方案**: 直接 logger + 让用户开 `-v` — 不够友好；Rich Live 嵌入 fetcher — 业务层与展示层耦合

**实现**: `FetchProgressEvent` dataclass，包含事件类型、mp_id、feed_name、detail。CLI 层通过回调更新 Rich Progress 的 task description。

### D4: 配置参数集中到 settings

新增配置项（均有合理默认值）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fetch_page_interval` | 6.0 | 列表翻页间隔 (s) |
| `fetch_article_interval` | 6.0 | 文章内容抓取间隔 (s) |
| `fetch_subscription_delay` | 8.0 | 订阅间基础等待 (s) |
| `fetch_subscription_jitter` | 4.0 | 订阅间抖动上限 (s) |
| `fetch_rate_limit` | 12 | 全局每分钟最大请求数 |
| `fetch_rate_window` | 60 | 滑动窗口大小 (s) |

## Risks / Trade-offs

- **[抓取耗时显著增加]** → 从 ~2 分钟增至 ~7 分钟。通过进度输出让用户知道在等什么。这是不可避免的代价。
- **[全局窗口可能在单订阅内就触发等待]** → 当单订阅文章很多时，窗口限制会额外增加等待。这是预期行为，保护性优先。
- **[回调参数侵入 fetcher 方法签名]** → 保持 Optional 默认 None，不影响现有调用方。
