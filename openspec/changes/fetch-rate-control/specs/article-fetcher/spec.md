## ADDED Requirements

### Requirement: FetcherService 集成速率限制器
FetcherService SHALL 在初始化时创建全局 `RateLimiter` 实例，并在所有外部 API 请求前调用 `acquire()`。

#### Scenario: fetch_all 中的速率控制
- **WHEN** `fetch_all()` 遍历订阅列表执行抓取
- **THEN** 每次发起列表页或文章内容请求前 SHALL 调用 `rate_limiter.acquire()`

#### Scenario: backfill 中的速率控制
- **WHEN** `backfill_publish_time()` 翻页获取文章列表
- **THEN** 每次翻页请求前 SHALL 调用 `rate_limiter.acquire()`

### Requirement: FetcherService 集成进度回调
FetcherService 的 `fetch_all()` 和 `_fetch_feed_summary()` SHALL 接受可选的 `on_progress` 回调参数，在关键节点发送进度事件。

#### Scenario: fetch_all 进度回调传递
- **WHEN** CLI 调用 `fetch_all(on_progress=callback)`
- **THEN** callback SHALL 在订阅开始、翻页、文章抓取、等待、订阅完成等节点被调用

#### Scenario: 单订阅抓取也支持进度回调
- **WHEN** CLI 调用 `fetch_feed(mp_id)` 或 `fetch_feed_summary(mp_id)`
- **THEN** SHALL 同样接受 on_progress 回调，在翻页和文章抓取节点触发
