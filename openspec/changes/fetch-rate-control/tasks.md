## 1. 配置与基础设施

- [x] 1.1 在 `config/settings.py` 新增 6 个配置项: `fetch_page_interval`、`fetch_article_interval`、`fetch_subscription_delay`、`fetch_subscription_jitter`、`fetch_rate_limit`、`fetch_rate_window`
- [x] 1.2 新建 `src/utils/rate_limiter.py`，实现 `RateLimiter` 类（滑动窗口、`async acquire()`）
- [x] 1.3 为 `RateLimiter` 编写单元测试

## 2. 进度事件机制

- [x] 2.1 在 `src/services/fetcher.py` 定义 `FetchProgressEvent` dataclass
- [x] 2.2 为 `FetchProgressEvent` 编写单元测试（构造与字段验证）

## 3. FetcherService 集成速率控制

- [x] 3.1 `FetcherService.__init__` 创建 `RateLimiter` 实例
- [x] 3.2 `_fetch_feed_summary` 在翻页循环中插入 `fetch_page_interval` 等待 + `rate_limiter.acquire()`
- [x] 3.3 `_fetch_feed_summary` 在文章循环中插入 `fetch_article_interval` 等待 + `rate_limiter.acquire()`（已存在文章跳过不等待）
- [x] 3.4 `fetch_all` 更新订阅间等待常量为 settings 配置值（`fetch_subscription_delay` + jitter）
- [x] 3.5 `backfill_publish_time` 在翻页循环中插入 `rate_limiter.acquire()`
- [x] 3.6 `_fetch_incremental_summary` 同样集成翻页和文章间隔控制

## 4. FetcherService 集成进度回调

- [x] 4.1 `fetch_all` 和 `_fetch_feed_summary` 接受 `on_progress` 参数
- [x] 4.2 在订阅开始、翻页、文章抓取/跳过/失败、等待、订阅完成等节点发送进度事件
- [x] 4.3 `fetch_all` 将 `on_progress` 传递给内部的 `_fetch_feed_summary` 调用

## 5. CLI 进度输出

- [x] 5.1 `subscription.py` 的 `fetch --all` 命令构建 `on_progress` 回调，替换原有的 SpinnerColumn
- [x] 5.2 实现回调渲染：订阅进度 `[N/total]`、翻页状态、文章状态、等待提示
- [x] 5.3 单订阅 `fetch <mp_id>` 命令同样接入进度回调

## 6. 测试与验证

- [x] 6.1 补充 fetcher 集成测试：验证间隔等待被正确调用
- [ ] 6.2 手动验证 `wchat fetch --all` 进度输出效果
