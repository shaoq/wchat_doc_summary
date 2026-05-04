## Context

已有限流熔断机制覆盖了 500 + `WeReadError400` 的场景。WeRead 代理还可能返回 401 + `WeReadError401`（Token 失效），这种情况同样无法通过重试解决。已有的熔断基础设施（`RateLimitError` → `fetch_feed` 上抛 → `fetch_all` 全局熔断 → CLI 提示）可以完全复用。

## Goals / Non-Goals

**Goals:**
- 复用现有熔断机制处理 401 Token 失效场景
- CLI 区分"限流"和"Token 失效"的提示信息

**Non-Goals:**
- 不实现自动刷新 Token
- 不改变 wechat2rss Provider 的行为

## Decisions

### D1: 新增 AuthExpiredError 而非复用 RateLimitError

Token 失效和限流虽然都是"不可恢复错误"，但语义不同：
- 限流 → 等一会儿就好
- Token 失效 → 需要重新登录

用不同异常类型让 CLI 能给出精准的恢复指引。

### D2: 在 _request() 中与限流检测并列

在已有的限流检测代码块之后，增加 401 检测。两者都在重试循环之前拦截，共享"不重试"语义。

### D3: fetcher.py 统一 catch

`fetch_feed`、`fetch_all`、`_get_latest_articles_with_retry` 中新增对 `AuthExpiredError` 的处理，逻辑与 `RateLimitError` 完全一致（上抛/熔断），。可以 catch 一个公共基类或用 tuple catch 两者。

## Risks / Trade-offs

- **[异常膨胀]** 新增 `AuthExpiredError` 增加了异常层级 → 只新增一个类，继承 `WeReadAPIError`，复用现有逻辑，可接受
- **[遗漏场景]** 未来可能还有其他不可恢复错误 → 检测逻辑集中在一处，便于扩展
