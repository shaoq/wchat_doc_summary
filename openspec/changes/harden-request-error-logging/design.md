## Context

RSS-backed fetches can call multiple external endpoints while processing one item: the RSS feed endpoint, the identity resolver provider, and sometimes the original WeChat article page. When an `httpx.RequestError` has an empty string representation, current logs lose the actionable part of the failure and make network problems look similar to token or attribution problems.

The affected paths are `WeReadClient._request()` and `fetch_article_content()`. `WeReadClient._request()` also accepts `max_retries_override`, but its `RequestError` branch currently compares attempts against `self.max_retries`, which can delay or suppress the intended terminal error when callers request a narrower retry window.

## Goals / Non-Goals

**Goals:**
- Make `httpx.RequestError` logs useful even when `str(error)` is blank.
- Include enough context to identify the failing request without leaking credentials or sensitive query parameters.
- Keep HTTP/token error handling separate from network-layer request errors.
- Ensure `max_retries_override` applies consistently to HTTP and request-error branches.

**Non-Goals:**
- Do not disable or change `RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS`.
- Do not change RSS attribution policy, unknown feed handling, source health semantics, or article persistence behavior.
- Do not introduce a new logging framework or external dependency.
- Do not print full tokens, API keys, cookies, or unredacted URLs.

## Decisions

1. Add a small shared request-error formatting helper.

   The helper should accept an `httpx.RequestError` and return a concise diagnostic string containing:
   - exception class name, for example `ConnectTimeout` or `ReadError`
   - message when non-empty
   - redacted request URL when `error.request.url` is available
   - cause class/message when `error.__cause__` is available

   Rationale: this keeps formatting consistent between `src/api/weread.py` and `src/api/article.py` without duplicating fragile string assembly. A local helper in an existing API utility module is enough; no new dependency is needed.

   Alternative considered: inline formatting in each caller. That is simpler initially but makes it easier for the two request paths to drift.

2. Redact URLs before logging.

   Existing RSS provider code already uses redaction for feed URLs. The implementation should reuse existing redaction behavior where practical, or introduce equivalent handling that masks sensitive query parameters such as `key`, `k`, `token`, `access_token`, and authorization-like values.

   Rationale: request diagnostics must help debug endpoint and host failures without exposing secrets in terminal output or logs.

3. Preserve current token-expiry control flow.

   `httpx.HTTPStatusError` handling that detects `WeReadError401` should remain distinct and continue raising `AuthExpiredError` immediately. The enhanced diagnostics apply to `httpx.RequestError`, not HTTP responses with status codes.

   Rationale: the user-facing troubleshooting distinction matters: token expiry requires login, while request errors usually point to network, proxy, TLS, timeout, or upstream availability.

4. Use the effective retry count in all terminal checks.

   `WeReadClient._request()` should compare `attempt == max_retries` in the `RequestError` branch, matching the HTTP error branch and honoring `max_retries_override`.

   Rationale: callers that intentionally narrow retries, such as fallback or probing flows, need deterministic behavior.

## Risks / Trade-offs

- More detailed logs may be noisier during transient outages → Keep each retry log single-line and concise.
- Redaction gaps could leak future credential parameter names → Cover common names and prefer existing redaction helpers when available.
- Tests that assert exact log strings may need updates → Add focused assertions on required diagnostic fragments instead of brittle full-line matches.
