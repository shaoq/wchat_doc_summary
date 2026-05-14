## Why

RSS imports currently can create incorrect local public-account subscriptions when a feed item does not expose reliable account metadata. In practice, some WeChat RSS items only provide article-level fields, causing fallback logic to derive the owning public account from article titles or URL hashes and produce subscriptions that do not match the existing `wchat subscribe` identity format.

This change makes RSS article ownership URL-driven: the system should use the WeChat original article URL to resolve the canonical public account, and only invoke the legacy subscribe-compatible resolver when a public account is unknown locally.

## What Changes

- Add URL-based RSS public-account attribution before article persistence.
- Prefer existing local article/feed mappings and cached account identities before invoking any external subscription resolver.
- Use the existing subscribe-compatible article URL resolution path for first-time unknown public accounts so auto-created subscriptions preserve the same identity shape as user-created subscriptions.
- Keep RSS article source/category membership separate from canonical public-account ownership.
- Prevent title/content-derived pseudo public accounts from being created by default.
- Make `wchat fetch` the unified article acquisition command for RSS-backed fetching.
- Deprecate or remove `wchat fetch MP_WXS_xxx` in the RSS-first workflow; article acquisition becomes source-wide rather than public-account-specific.
- Stop using public-account/date batch progress as the RSS fetch progress model; RSS imports should be idempotent through source health tracking and article deduplication.
- Add diagnostics for discovered, resolved, skipped, and failed RSS ownership resolution outcomes.
- Define a cleanup path for already-created incorrect RSS pseudo feeds by re-resolving their article URLs and moving articles to the correct canonical feed when possible.

## Capabilities

### New Capabilities
- `rss-feed-attribution`: URL-based public-account attribution for RSS-imported articles, including cached identity matching, subscribe-compatible first discovery, and failure policy behavior.
- `fetch-command-rss-mode`: Unified `wchat fetch` behavior for RSS-backed article acquisition, including source-wide sync semantics and deprecated single-public-account fetch behavior.

### Modified Capabilities
- `subscription`: RSS-discovered public accounts must preserve subscribe-compatible identity when discovered from article URLs, and must not be created from article-title/content guesses by default.
- `article-fetcher`: RSS-backed article import must resolve canonical feed ownership through URL-based attribution before persistence, and RSS-backed fetching must not rely on per-public-account date batch progress.

## Impact

- Affected code:
  - RSS fetch/import flow in `FetcherService`
  - CLI fetch command behavior and help text
  - RSS feed discovery and auto-subscribe logic
  - Provider/subscription resolution path used by `wchat subscribe`
  - Feed/article source membership persistence
  - CLI fetch diagnostics and possibly repair/maintenance commands
- External dependencies:
  - WeChat RSS SaaS remains the primary article-list source.
  - WeChat login or existing subscribe-compatible provider credentials may be used only for first-time unknown public-account resolution.
- Data impact:
  - New or reused local identity mapping is needed to avoid repeated subscription resolution for every article.
  - Existing incorrect `rss:<hash>` pseudo subscriptions may need migration or cleanup.
- Compatibility:
  - Existing RSS source configuration and single API key behavior remain unchanged.
  - `wchat fetch --all` may remain as a compatibility alias, but `wchat fetch` becomes the preferred daily command.
  - `wchat fetch MP_WXS_xxx` is no longer part of the RSS-first article acquisition model.
  - Existing user-created subscriptions remain canonical and should be reused when RSS items belong to those public accounts.
