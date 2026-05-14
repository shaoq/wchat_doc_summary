## Why

Current public-account article fetching still depends on direct WeRead/WeChat-facing discovery paths that frequently hit upstream rate limits. If the system adopts a paid WeChat RSS SaaS source, `wchat` should stop acting as the primary crawler and instead consume stable RSS feeds as upstream content sources.

This change moves the risky article discovery and polling responsibility to WeChat RSS SaaS, while keeping `wchat` focused on local persistence, deduplication, AI processing, export, and operational visibility.

## What Changes

- Add a generic RSS article-list provider suitable for WeChat RSS SaaS aggregate/category feeds and other standard RSS-compatible sources.
- Store one or more local RSS sources, each with its own RSS URL, while using one global WeChat RSS API key from settings.
- Support both a single aggregate RSS source such as `全部` and multiple category RSS sources such as `财经` or `科技`.
- Import articles from RSS sources, infer or reconcile their public-account identity, and preserve source/category membership separately from article identity when category information exists.
- Make RSS-backed fetching cache-first: use feed-provided article content when available and avoid direct `mp.weixin.qq.com` content requests unless explicitly configured.
- Add source health tracking for RSS feeds, including stale feeds, consecutive failures, empty responses, and last successful fetch time.
- Add plan/quota awareness for paid WeChat RSS SaaS tiers so the system can warn before local RSS category sources exceed the configured provider limit when a limit is configured.
- Preserve existing WeRead and Wechat2RSS behavior as compatibility paths; this change does not remove them.

## Capabilities

### New Capabilities
- `rss-source-health`: Tracks RSS upstream health, staleness, and paid-plan quota state for SaaS-backed RSS sources.

### Modified Capabilities
- `article-list-provider`: Add a generic RSS provider that can consume WeChat RSS SaaS feeds and normalize RSS items into provider article items.
- `subscription`: Store and display RSS sources, source-to-public-account associations, and category/source-aware list views.
- `article-fetcher`: Prefer feed-provided content for RSS-backed providers and only fetch article pages directly when configured to do so.

## Impact

- Affected code areas:
  - Provider abstraction and factory under `src/api/providers/`
  - Subscription creation, storage, and listing logic
  - Fetcher content import path and article deduplication
  - CLI commands for subscription/import/diagnostics
  - Settings for RSS mode, SaaS plan limit, stale thresholds, and direct-fetch fallback behavior
- Data impact:
  - RSS sources need persistent `name`, `feed_url`, source type, provider metadata, and health state.
  - Articles imported from RSS sources need source membership tracking so one article or public account can belong to a single aggregate source or multiple category sources without duplicate article rows.
  - Source health may require a new table or explicit fields if existing metadata is insufficient.
- External systems:
  - WeChat RSS SaaS remains responsible for public-account polling and RSS generation.
  - `wchat` should treat SaaS RSS as the upstream content source and minimize direct requests to WeChat article pages.
