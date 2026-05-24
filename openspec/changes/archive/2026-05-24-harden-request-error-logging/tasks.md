## 1. Diagnostics Helper

- [x] 1.1 Locate or create a small shared helper for formatting `httpx.RequestError` diagnostics.
- [x] 1.2 Include exception class, non-empty message, redacted request URL, and lower-level cause details in the formatted diagnostic.
- [x] 1.3 Ensure URL redaction masks common sensitive query parameters while preserving host and path.

## 2. Request Handling Updates

- [x] 2.1 Update `src/api/weread.py` to use the enhanced diagnostic in `RequestError` retry logs and terminal `WeReadAPIError`.
- [x] 2.2 Fix `WeReadClient._request()` so the `RequestError` terminal check compares against the effective `max_retries` value.
- [x] 2.3 Update `src/api/article.py` to use the enhanced diagnostic in article content fetch retry logs and terminal `ArticleFetchError`.
- [x] 2.4 Confirm `WeReadError401` handling still raises `AuthExpiredError` without being logged as a generic request error.

## 3. Tests

- [x] 3.1 Add regression coverage for blank-message `httpx.RequestError` logs including exception class and redacted URL.
- [x] 3.2 Add regression coverage for request errors with lower-level causes.
- [x] 3.3 Add coverage proving `max_retries_override=0` raises after the first request-error attempt.
- [x] 3.4 Add or preserve coverage proving token-expiry responses remain distinct from request errors.

## 4. Verification

- [x] 4.1 Run the focused request/API tests affected by the change.
- [x] 4.2 Run the relevant RSS attribution or fetch tests to ensure behavior remains unchanged.
- [x] 4.3 Run OpenSpec validation/status checks for `harden-request-error-logging`.
