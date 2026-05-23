## Why

RSS fetch currently surfaces some network failures as blank messages such as `请求错误 (尝试 1):` and `网络请求失败:`. This makes it hard to distinguish token expiry from DNS, timeout, TLS, proxy, or connection failures when RSS attribution or article-page fallback requests fail.

## What Changes

- Add structured diagnostics for `httpx.RequestError` handling so retry logs include the exception type, a redacted request URL when available, and the underlying cause when available.
- Preserve the current RSS auto-subscribe behavior; this change SHALL NOT disable or recommend disabling `RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS`.
- Fix `WeReadClient._request()` so `RequestError` retry exhaustion honors the effective retry count from `max_retries_override`, not `self.max_retries`.
- Keep token-expiry handling distinct: HTTP responses containing `WeReadError401` continue to raise `AuthExpiredError` and should remain visibly different from network-layer request errors.

## Capabilities

### New Capabilities
- `request-error-diagnostics`: Covers diagnostic output and retry semantics for network request failures in WeRead API and article content fetch paths.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/api/weread.py`
  - `src/api/article.py`
  - Potential shared helper location if implementation chooses to centralize request-error formatting.
- Affected tests:
  - Existing API/request tests around retry behavior.
  - New regression tests for blank `RequestError` messages and `max_retries_override` exhaustion.
- No database schema changes.
- No CLI flag or environment variable changes.
- No RSS source, attribution policy, or subscription behavior changes beyond clearer diagnostics for failures.
