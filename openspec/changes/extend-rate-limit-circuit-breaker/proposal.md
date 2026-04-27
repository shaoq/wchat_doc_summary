## Why

WeRead 代理返回 401 `WeReadError401`（Token 失效）时，当前代码将其当作普通 API 错误进行重试，毫无意义。Token 失效和限流一样属于"不可恢复错误" — 需要人工介入（重新登录），应复用已有的熔断机制立即中断。

## What Changes

- 在 `WeReadClient._request()` 中新增 401 + `WeReadError401` 的检测，抛出 `AuthExpiredError`
- `AuthExpiredError` 继承 `WeReadAPIError`，与 `RateLimitError` 平级，复用已有的熔断传播逻辑
- CLI 层区分限流和 Token 失效的提示信息（"请稍后重试" vs "请重新登录: wchat login"）

## Capabilities

### New Capabilities
- `auth-expired-circuit-breaker`: Token 失效 (401) 的快速中断与用户提示

### Modified Capabilities
- `rate-limit-circuit-breaker`: 扩展熔断传播逻辑，同时处理 `AuthExpiredError` 和 `RateLimitError`

## Impact

- **代码**: `src/api/weread.py`（新增异常 + 检测）、`src/services/fetcher.py`（扩展 catch 范围）、`src/cli/subscription.py`（区分提示）
- **依赖**: 无新增依赖
- **行为变更**: 401 Token 失效时不再重试，立即中断并提示重新登录
