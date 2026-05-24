## Why

After request-error diagnostics were added to WeRead and article-page fetch paths, `wchat fetch --all` can still fail with `RSS 源抓取失败: <source> -` when the RSS feed request itself raises an empty-message network exception. The RSS feed provider is the first network hop in RSS mode, so it needs the same diagnostic treatment to identify feed endpoint, timeout, DNS, TLS, proxy, or HTTP-status failures.

## What Changes

- Add actionable diagnostics to `RSSProvider._fetch_feed()` for `httpx.RequestError` failures.
- Convert RSS feed HTTP status failures into `RSSProviderError` messages that include status code and redacted feed URL context.
- Ensure outer RSS fetch failure logging and RSS source health records receive non-empty failure summaries.
- Reuse the existing request-error formatting/redaction behavior where possible.
- Preserve current RSS mode behavior, including `RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS`; this change does not disable auto-subscribe or change attribution policy.

## Capabilities

### New Capabilities
- `rss-feed-request-diagnostics`: Covers diagnostic output and source-health failure summaries for RSS feed endpoint request failures.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/api/providers/rss_provider.py`
  - Potentially tests around RSS provider error handling and RSS source failure reporting.
- No database schema changes.
- No CLI flag or environment variable changes.
- No changes to RSS attribution, token handling, subscription behavior, or article persistence.
