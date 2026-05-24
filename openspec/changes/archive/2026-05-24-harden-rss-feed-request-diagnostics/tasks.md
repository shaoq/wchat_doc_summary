## 1. Provider Error Handling

- [x] 1.1 Update `RSSProvider._fetch_feed()` to catch `httpx.RequestError` and raise `RSSProviderError` with enhanced request diagnostics.
- [x] 1.2 Update `RSSProvider._fetch_feed()` to catch `httpx.HTTPStatusError` and raise `RSSProviderError` with HTTP status code and redacted feed URL.
- [x] 1.3 Ensure feed URLs with API keys or token-like query parameters are redacted in all new RSS provider error messages.

## 2. Failure Propagation

- [x] 2.1 Verify `FetcherService.fetch_from_rss_sources()` logs a non-empty message when RSS feed fetch fails.
- [x] 2.2 Verify `RSSSourceService.record_failure()` receives a non-empty diagnostic summary for RSS feed request failures.
- [x] 2.3 Preserve existing RSS parsing failure behavior for malformed feeds.

## 3. Tests

- [x] 3.1 Add RSS provider regression coverage for empty-message `httpx.RequestError`.
- [x] 3.2 Add RSS provider coverage for request errors with lower-level causes.
- [x] 3.3 Add RSS provider coverage for HTTP status failures including status code and redacted URL.
- [x] 3.4 Add fetch orchestration coverage proving source failure summaries are non-empty for RSS feed request failures.

## 4. Verification

- [x] 4.1 Run focused RSS provider and RSS fetch tests.
- [x] 4.2 Run OpenSpec status or validation checks for `harden-rss-feed-request-diagnostics`.
