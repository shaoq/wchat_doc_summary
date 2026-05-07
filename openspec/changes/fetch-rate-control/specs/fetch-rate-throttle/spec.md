## ADDED Requirements

### Requirement: 滑动窗口速率限制器
系统 SHALL 提供 `RateLimiter` 类，基于滑动窗口限制请求密度。窗口大小和最大请求数通过构造参数配置。

#### Scenario: 窗口内未达上限时立即放行
- **WHEN** 调用 `acquire()` 且窗口内已记录的请求数 < max_requests
- **THEN** SHALL 记录当前时间戳并立即返回

#### Scenario: 窗口内达到上限时等待
- **WHEN** 调用 `acquire()` 且窗口内已记录的请求数 >= max_requests
- **THEN** SHALL 计算最早请求退出窗口的剩余时间，sleep 等待后重试

#### Scenario: 过期时间戳自动清理
- **WHEN** 调用 `acquire()`
- **THEN** SHALL 先移除所有早于 (当前时间 - window_size) 的时间戳

### Requirement: 列表翻页间隔
FetcherService 在分页获取文章列表时，SHALL 在每次翻页请求前等待可配置的间隔（`fetch_page_interval`），第一页不等待。

#### Scenario: 翻页间等待
- **WHEN** 循环获取第 N 页（N > 1）的文章列表
- **THEN** SHALL 在发起请求前等待 `fetch_page_interval` 秒（默认 6.0s）

#### Scenario: 第一页不等待
- **WHEN** 获取第 1 页文章列表
- **THEN** SHALL 不等待，直接请求

### Requirement: 文章内容抓取间隔
FetcherService 在抓取单篇文章内容时，SHALL 在每篇文章请求后等待可配置的间隔（`fetch_article_interval`）。跳过已存在的文章时不触发等待。

#### Scenario: 新文章抓取后等待
- **WHEN** 成功抓取并保存一篇新文章
- **THEN** SHALL 等待 `fetch_article_interval` 秒（默认 6.0s）

#### Scenario: 已存在文章跳过不等待
- **WHEN** 文章已存在于数据库中（状态为 "existing"）
- **THEN** SHALL 不等待，直接处理下一篇

#### Scenario: 文章抓取失败后仍等待
- **WHEN** 单篇文章抓取失败（状态为 "failed"）
- **THEN** SHALL 仍等待 `fetch_article_interval` 秒，避免失败后立即重试加剧限流

### Requirement: 订阅间等待间隔
FetcherService.fetch_all() 在订阅切换时 SHALL 等待 `fetch_subscription_delay` + random(0, `fetch_subscription_jitter`) 秒。

#### Scenario: 正常订阅切换等待
- **WHEN** 完成一个订阅后切换到下一个（非最后一个）
- **THEN** SHALL 等待 `fetch_subscription_delay` + jitter 秒（默认 8.0 + 0~4.0s）

#### Scenario: 最后一个订阅不等待
- **WHEN** 处理完最后一个订阅
- **THEN** SHALL 不等待

#### Scenario: 异常后退避
- **WHEN** 某订阅抓取抛出非 RateLimitError/AuthExpiredError 异常
- **THEN** 下一次订阅间等待 SHALL 使用 min(delay * BACKOFF_FACTOR, 60.0) 的退避策略

### Requirement: 全局速率限制集成
所有外部 API 请求（列表页、文章内容、回填）SHALL 通过全局 RateLimiter 的 `acquire()` 方法，确保总请求密度不超过配置的上限。

#### Scenario: 所有请求经过 RateLimiter
- **WHEN** fetcher 发起列表页或文章内容请求
- **THEN** SHALL 先调用 `rate_limiter.acquire()`，获得许可后才发请求

#### Scenario: backfill 请求也受限
- **WHEN** backfill_publish_time 翻页获取列表
- **THEN** SHALL 同样通过全局 RateLimiter 控制

### Requirement: 间隔参数可配置
所有间隔参数 SHALL 通过 config/settings.py 配置，支持环境变量覆盖。

#### Scenario: 参数来源
- **WHEN** fetcher 初始化
- **THEN** SHALL 从 `get_settings()` 读取 `fetch_page_interval`、`fetch_article_interval`、`fetch_subscription_delay`、`fetch_subscription_jitter`、`fetch_rate_limit`、`fetch_rate_window` 参数
