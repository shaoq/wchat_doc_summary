## Why

微信读书 API 返回 Token 失效时，HTTP 状态码为 500（而非 401），导致现有检测逻辑未识别为认证过期。结果是 `fetch --all` 在所有订阅上反复重试失败，浪费时间且未提示用户重新登录。

## What Changes

- 修改 `WeReadClient._request()` 中的 Token 失效检测：从"状态码 401 + body 含 WeReadError401"改为"仅判断 body 含 WeReadError401"，不依赖 HTTP 状态码

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `rate-limit-circuit-breaker`: 扩展不可恢复错误检测，将 HTTP 500 + `WeReadError401` 也识别为认证过期

## Impact

- `src/api/weread.py` — `_request()` 方法的异常分类逻辑
- `src/services/fetcher.py` — 无需改动，已有 `AuthExpiredError` 的 break 分支
- `src/cli/subscription.py` — 无需改动，已有 `AuthExpiredError` 的用户提示
