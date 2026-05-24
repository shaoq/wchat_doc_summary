## Context

RSS 模式的文章归属通过 `RSSAttributionService` 实现，其中 Tier 4（`_subscribe_compatible_resolve`）调用 WeRead API 从文章 URL 解析公众号身份。当 WeRead Token 失效时，该 API 返回 401，`WeReadClient` 抛出 `AuthExpiredError`。

当前错误传播链：

```
_subscribe_compatible_resolve()
  → except Exception as e:     ← 吞掉 AuthExpiredError
      log warning
      return None

_fetch_and_save_rss_article()
  → attribution_service.attribute()
      → 无异常，返回 None → 文章标记 failed

_fetch_rss_source()
  → for each article: 循环继续

fetch_from_rss_sources()
  → except Exception as e:     ← 捕获 RSSProviderError 等非 Auth 错误
      record_failure()
      continue 下一源
```

对比 WeRead 模式 `fetch_all` 中 `AuthExpiredError` 会触发 `break`，立即终止整个批量抓取。RSS 模式缺少这条传播路径。

## Goals / Non-Goals

**Goals:**
- `AuthExpiredError` 在 RSS 归属路径中不被静默吞掉，而是向上传播。
- RSS 模式遇到 `AuthExpiredError` 时立即中断当前源和后续源的处理。
- 行为与 WeRead 模式一致：不可恢复的全局错误应终止整个抓取会话。
- 用户在终端看到明确的 Token 失效提示，而非重复刷屏的失败日志。

**Non-Goals:**
- 不改变 RSS feed 请求、feed 解析、文章标准化、去重、内容模式等行为。
- 不改变 Tier 1-3（本地匹配）的逻辑，这些路径不涉及 WeRead API。
- 不添加 Token 自动刷新或重新登录机制。
- 不改变 `RateLimitError` 的处理方式。

## Decisions

1. 在 `_subscribe_compatible_resolve` 中将 `AuthExpiredError` 从宽泛的 `except Exception` 中分离出来并 `raise`。

   Rationale: `AuthExpiredError` 是全局不可恢复错误，不应被降级为单篇文章的归属失败。让异常沿调用栈自然向上传播是最简单的方案。

   Alternative: 在归属层捕获并记录，设置一个标志位让外层检查。更复杂且不必要——Python 的异常机制已经提供了这一功能。

2. 在 `_fetch_rss_source` 的文章循环中捕获 `AuthExpiredError` 并向上传播。

   Rationale: `_fetch_and_save_rss_article` 捕获了 `Exception` 并返回 `("failed", None)`，会吞掉 `AuthExpiredError`。需要在循环层将 `AuthExpiredError` 分离出来重新抛出。

   Alternative: 修改 `_fetch_and_save_rss_article` 的签名让它传播 `AuthExpiredError`。但这会改变该方法的异常契约，影响面更大。在循环层捕获更局部。

3. 在 `fetch_from_rss_sources` 的源循环中，对 `AuthExpiredError` 执行 `break`（类似 `fetch_all` 的处理方式），对其他异常继续 `record_failure` + 继续下一源。

   Rationale: Token 失效影响所有后续源的 Tier 4 归属，继续处理没有实际收益。与 `fetch_all` 的行为保持一致。

4. 不引入新的异常类型或状态标志。

   Rationale: `AuthExpiredError` 已在 `fetch_all`（WeRead 模式）中使用，直接复用即可。不需要为 RSS 模式发明新的信号机制。

## Risks / Trade-offs

- `_fetch_rss_source` 文章循环中需要额外的 `except AuthExpiredError` 分支，增加循环体的复杂度 → 影响极小，只多了一个 `except` 子句。
- 如果某篇文章 Tier 1-3 可以匹配但尚未走到 Tier 4 就触发了 401，该文章不会被处理 → 可接受：Token 失效后应该立即让用户知道并重新登录，而不是在降级模式下继续跑。
- 归属路径中的 `AuthExpiredError` 可能源于 Tier 4 的首次调用，也可能是后续调用 → 不影响，遇到即中断，无需区分首次和后续。
