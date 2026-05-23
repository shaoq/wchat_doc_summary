## Context

`wchat fetch --all` in RSS mode starts by requesting each active RSS source through `RSSProvider._fetch_feed()`. When that request fails with an empty-message `httpx.RequestError`, the exception bubbles up to `FetcherService.fetch_from_rss_sources()`, where `str(error)` is logged and stored as the source failure summary. The result is a blank message such as `RSS 源抓取失败: 分类51 -`, which does not identify the RSS endpoint failure mode.

The prior `harden-request-error-logging` change added a reusable request-error formatter and covered WeRead/article-page requests. This follow-up applies the same diagnostic standard to the RSS feed provider itself.

## Goals / Non-Goals

**Goals:**
- Ensure RSS feed request failures produce non-empty diagnostics.
- Include request-error class, redacted feed URL, and lower-level cause when available.
- Convert HTTP status failures from RSS feed requests into clear `RSSProviderError` messages.
- Ensure RSS source health records receive useful failure summaries.

**Non-Goals:**
- Do not change feed parsing, article normalization, pagination, or deduplication behavior.
- Do not change `RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS`, RSS attribution, or unknown feed policy.
- Do not add new retry behavior for RSS feed requests unless already present in the code.
- Do not expose RSS API keys or token-like query parameters in logs.

## Decisions

1. Handle RSS provider network failures at the provider boundary.

   `RSSProvider._fetch_feed()` should catch `httpx.RequestError` and raise `RSSProviderError` with the enhanced diagnostic string.

   Rationale: callers of `RSSProvider` already understand `RSSProviderError`; converting at the provider boundary keeps outer fetch orchestration simple and ensures source health receives a meaningful string.

   Alternative considered: formatting in `FetcherService.fetch_from_rss_sources()`. That would require the orchestration layer to understand provider-specific network exceptions and would not help direct provider callers.

2. Convert HTTP status failures into `RSSProviderError`.

   `httpx.HTTPStatusError` should be caught near `response.raise_for_status()` and converted into a message containing the HTTP status code and redacted URL.

   Rationale: RSS feed endpoint failures such as 401, 403, 404, 429, and 5xx are operationally different from parsing failures and should be visible without a traceback.

3. Reuse existing redaction/formatting behavior.

   Prefer the existing `format_request_error()` helper for `RequestError`, and use existing URL redaction behavior for feed URLs. The implementation should avoid creating a second incompatible redaction policy.

   Rationale: diagnostics should be consistent across WeRead, article-page, and RSS feed requests.

## Risks / Trade-offs

- Wrapping exceptions changes the visible exception type for direct RSS provider callers → Use `RSSProviderError`, which is already the provider-specific error type.
- HTTP response body might contain useful upstream details → Keep this change focused on safe status and URL diagnostics; do not log full bodies unless separately reviewed for leakage risk.
- Duplicate redaction helpers already exist → Prefer reuse during implementation if practical, but do not broaden this follow-up into a larger refactor.
