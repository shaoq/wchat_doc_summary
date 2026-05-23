## 1. Attribution Error Propagation

- [x] 1.1 Update `RSSAttributionService._subscribe_compatible_resolve()` to re-raise `AuthExpiredError` instead of catching it in the generic `except Exception` handler.
- [x] 1.2 Verify that non-auth exceptions in `_subscribe_compatible_resolve()` continue to return `None` and log a warning unchanged.

## 2. Source-Level Abort

- [x] 2.1 Update `_fetch_rss_source()` article loop to catch `AuthExpiredError` and re-raise it, stopping the loop before processing remaining articles.
- [x] 2.2 Verify that `_fetch_rss_source()` preserves successfully processed articles when `AuthExpiredError` interrupts the loop.

## 3. Session-Level Abort

- [x] 3.1 Update `fetch_from_rss_sources()` source loop to catch `AuthExpiredError` separately from `Exception`, record failure, and `break` to stop remaining sources.
- [x] 3.2 Verify that non-auth exceptions in `fetch_from_rss_sources()` continue to `record_failure()` and proceed to the next source.

## 4. Tests

- [x] 4.1 Add attribution test proving `AuthExpiredError` propagates from `_subscribe_compatible_resolve` (not swallowed).
- [x] 4.2 Add attribution test proving non-auth exceptions still return `None` unchanged.
- [x] 4.3 Add source-level test proving `_fetch_rss_source` stops article loop on `AuthExpiredError` and preserves earlier articles.
- [x] 4.4 Add session-level test proving `fetch_from_rss_sources` breaks source loop on `AuthExpiredError`.

## 5. Verification

- [x] 5.1 Run focused RSS attribution and RSS fetch tests.
- [x] 5.2 Run OpenSpec validation for `abort-rss-fetch-on-auth-expired`.
