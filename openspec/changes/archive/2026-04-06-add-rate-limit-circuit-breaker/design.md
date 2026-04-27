## Context

当前系统通过 `WeReadClient` 调用 `weread.111965.xyz` 代理获取公众号文章列表。该代理在限流时返回 HTTP 500 + `WeReadError400`。现有重试机制（无间隔的 3 次重试）和 narrow-retry（缩小 page_size 重试）对限流场景不仅无效，反而加剧问题。`fetch_all` 批量模式下，一个订阅限流后仍继续请求其他订阅，导致全部失败。

涉及三层代码：
- `src/api/weread.py` — HTTP 客户端，`_request()` 方法
- `src/services/fetcher.py` — 业务编排，`fetch_feed()` / `fetch_all()`
- `src/cli/subscription.py` — CLI 层，`fetch` 命令

## Goals / Non-Goals

**Goals:**
- 识别 WeRead 代理的限流响应，立即停止请求
- 单订阅抓取（`fetch_feed`）限流时直接停止，不重试
- 批量抓取（`fetch_all`）限流时停止遍历，返回已完成部分
- CLI 输出清晰的限流提示和恢复指引
- 限流后必须手动重新触发

**Non-Goals:**
- 不实现自动退避/冷却后恢复（完全依赖手动触发）
- 不实现持久化熔断状态（进程内即生即灭）
- 不改变其他 Provider（wechat2rss）的行为
- 不实现限流前的主动预防（如请求间隔控制）

## Decisions

### D1: 限流异常独立于 WeReadAPIError

在 `WeReadAPIError` 之外新增 `RateLimitError` 子类。

**理由**: 限流是可预期的业务状态，不是通用 API 错误。调用方需要区分"网络错误 / 参数错误"和"被限流了"。用子类保持 `isinstance` 兼容。

**替代方案**: 在 `WeReadAPIError` 上加 `is_rate_limited` 属性 — 可行但不如异常类型直观，且需要每层手动检查属性。

### D2: 限流检测在 _request() 内部、重试循环之前

在 `_request()` 的 HTTP 响应检查中，先判断是否为限流响应，若是则直接抛出 `RateLimitError`，不进入 for 循环的重试逻辑。

**理由**: 限流时重试无意义，应在最低层拦截，避免浪费请求次数。

### D3: fetch_all 限流后立即停止（全局熔断）

`fetch_all()` 捕获 `RateLimitError` 后跳出循环，不继续请求其他订阅。

**理由**: 同一个 WeRead token 下的限流是全局性的，继续请求其他订阅只会加重限制。返回已完成的部分结果，供用户参考。

### D4: _get_latest_articles_with_retry 也拦截限流

当前 narrow-retry 在 `WeReadAPIError` 时缩小 page_size 重试。新增对 `RateLimitError` 的直接上抛，不进入缩窗口逻辑。

## Risks / Trade-offs

- **[误判风险]** `WeReadError400` 可能不完全是限流，也可能是其他 400 类错误 → 当前仅此一种已知模式，可接受；后续如出现新模式再扩展检测条件
- **[中断粒度]** 批量模式下可能在第 1 个订阅就中断 → 这是预期行为，比全部失败更优；用户能看到 0/N 的进度提示
- **[非 WeRead Provider]** wechat2rss 不受影响 → 符合预期，不同 Provider 独立处理
