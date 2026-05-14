## 1. Data Model And Settings

- [ ] 1.1 Add settings for RSS provider selection, global WeChat RSS API key, RSS content mode, stale threshold, quota limit, and sensitive query redaction.
- [ ] 1.2 Add persistent storage for one or more named RSS sources, including provider, source name, source type, feed URL, status, and provider metadata.
- [ ] 1.3 Add persistent RSS source health storage for success time, latest item time, consecutive failures, empty response count, and last error summary.
- [ ] 1.4 Add membership storage so articles and inferred public accounts can be associated with one aggregate RSS source or multiple RSS category sources without duplicating canonical articles.
- [ ] 1.5 Add migration or compatibility logic so existing WeRead and Wechat2RSS subscriptions continue to fetch without manual changes.

## 2. RSS Provider

- [ ] 2.1 Add a generic RSS article-list provider implementation under the existing provider abstraction.
- [ ] 2.2 Parse RSS/Atom feed metadata and normalize item title, link, GUID/id, publish time, summary, and HTML content into provider article items.
- [ ] 2.3 Route RSS provider fetches through each configured RSS source feed URL rather than through per-public-account feed URLs.
- [ ] 2.4 Apply the single global WeChat RSS API key from settings when RSS source fetches require authentication.
- [ ] 2.5 Redact sensitive feed URL query values and API key values in logs and diagnostics.
- [ ] 2.6 Register the RSS provider in the provider factory and configuration validation.

## 3. Source And Subscription Flows

- [ ] 3.1 Add commands or service methods to add, list, update, disable, and remove RSS sources, including a single aggregate source such as `全部`.
- [ ] 3.2 Infer or reconcile public-account identity from RSS item metadata, author fields, or original article pages when available.
- [ ] 3.3 Store SaaS provider metadata required for future source fetches and diagnostics without storing the global API key in source records.
- [ ] 3.4 Preserve source membership when a public account or article appears in one aggregate source or multiple RSS category sources.
- [ ] 3.5 Add active RSS source counting for plan quota checks.

## 4. Fetch Pipeline

- [ ] 4.1 Implement RSS cache-first article import that uses feed-provided HTML content without requesting the original WeChat article page.
- [ ] 4.2 Implement `feed_only`, `prefer_feed`, and `fetch_missing` content-mode behavior.
- [ ] 4.3 Ensure RSS-backed article deduplication uses provider item identity and original URL before insert.
- [ ] 4.4 Attach imported articles to RSS source membership for every source where they appear.
- [ ] 4.5 Update RSS source health state on feed success, empty response, stale source, transport failure, and parse failure.
- [ ] 4.6 Keep direct article-page fallback subject to existing throttling and error handling when fallback is enabled.

## 5. CLI And Diagnostics

- [ ] 5.1 Add CLI output for RSS source health, including stale state, last success, consecutive failures, empty response count, and redacted source identifier.
- [ ] 5.2 Extend `wchat ls` with public-account view that shows associated RSS source names or categories when RSS-backed identity can be inferred.
- [ ] 5.3 Add a source list view that groups by configured RSS source and shows health plus associated public accounts or article counts.
- [ ] 5.4 Add quota warning output when active RSS source count exceeds the configured paid SaaS plan limit.
- [ ] 5.5 Ensure normal fetch output distinguishes no-new-articles from upstream RSS source failure or staleness.

## 6. Tests And Verification

- [ ] 6.1 Add provider unit tests for RSS item normalization, source feed URL routing, single aggregate source behavior, content extraction, global API key usage, and URL redaction.
- [ ] 6.2 Add source/subscription tests for RSS source creation, metadata persistence, public-account inference, aggregate source membership, multi-category membership, and quota counting.
- [ ] 6.3 Add fetcher tests for cache-first import, content modes, deduplication by provider item and URL, category membership attachment, and fallback behavior.
- [ ] 6.4 Add CLI tests for default `ls`, source view, aggregate source display, category source display, and source health diagnostics.
- [ ] 6.5 Add health diagnostics tests for success, failure, empty response, stale source, and quota warning scenarios.
- [ ] 6.6 Run the relevant test suite and OpenSpec validation for `integrate-wechat-rss-saas-provider`.
