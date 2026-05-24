## Why

RSS 模式下，当 WeRead Token 失效（HTTP 401）时，`_subscribe_compatible_resolve` 使用宽泛的 `except Exception` 捕获了 `AuthExpiredError` 并静默返回 `None`。这导致每篇文章都重复触发 401 失败，日志刷屏且全部文章标记为 failed，没有任何实际产出。WeRead 模式已经对 `AuthExpiredError` 做了立即中断处理，但 RSS 模式的归属路径缺少同样的保护。

## What Changes

- 让 `RSSAttributionService._subscribe_compatible_resolve()` 将 `AuthExpiredError` 向上传播而非静默吞掉。
- 让 `FetcherService.fetch_from_rss_sources()` 在捕获到 `AuthExpiredError` 时立即中断剩余源的处理，记录失败并提示用户重新登录。
- 让 `_fetch_rss_source()` 中的归属路径将 `AuthExpiredError` 向上传播，确保中断信号不被文章循环吞掉。
- 与 WeRead 模式保持一致：`AuthExpiredError` 是不可恢复的全局错误，应立即终止整个抓取会话。

## Capabilities

### New Capabilities
- `rss-auth-expired-abort`: 覆盖 RSS 模式下 WeRead Token 失效时的即时中断行为，包括归属路径异常传播和源级循环中断。

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/services/rss_attribution.py` — `_subscribe_compatible_resolve` 异常处理
  - `src/services/fetcher.py` — `fetch_from_rss_sources` 和 `_fetch_rss_source` 异常处理
  - Potentially tests around RSS attribution and RSS fetch orchestration.
- No database schema changes.
- No CLI flag or environment variable changes.
- No changes to RSS feed request diagnostics, feed parsing, article normalization, or deduplication behavior.
