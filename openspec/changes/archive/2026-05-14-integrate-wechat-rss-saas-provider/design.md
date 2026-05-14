## Context

The current fetch pipeline already has an `ArticleListProvider` abstraction and a `Wechat2RSS` provider, but the default operational model still treats `wchat` as the component responsible for public-account discovery and article-page fetching. That keeps the system exposed to upstream WeRead and `mp.weixin.qq.com` rate limits.

With a paid WeChat RSS SaaS source, the cleaner boundary is different: the SaaS service owns public-account polling and RSS generation, while `wchat` consumes the resulting RSS feeds as upstream content. The local application should then focus on persistence, deduplication, AI processing, export, health visibility, and controlled fallback behavior.

## Goals / Non-Goals

**Goals:**

- Add a generic RSS article-list provider that can consume WeChat RSS SaaS aggregate/category feeds without binding the codebase to one vendor-specific API.
- Support one global WeChat RSS API key in settings and one or more local RSS sources, each with its own RSS URL.
- Support a single aggregate source such as `全部` as the simplest configuration, while allowing multiple category sources when the user wants category-level membership.
- Import articles from RSS feeds, infer public-account identity from feed items where possible, and preserve source/category membership separately from article identity when category information exists.
- Prefer RSS-provided title, URL, publish time, summary, and content HTML when importing articles.
- Avoid direct WeChat article-page fetches for RSS-backed subscriptions unless a configuration explicitly enables fallback.
- Track RSS source health and paid-plan quota state so SaaS feed issues are visible before downstream workflows silently degrade.
- Keep WeRead and existing Wechat2RSS behavior available for compatibility.

**Non-Goals:**

- Do not implement or host the WeChat RSS SaaS service inside this project.
- Do not scrape WeChat public accounts directly as part of this change.
- Do not remove existing WeRead or Wechat2RSS providers.
- Do not redesign AI processing, export, or market-summary flows.
- Do not guarantee that a third-party SaaS feed is complete; `wchat` can only reflect feed health and import what the upstream exposes.

## Decisions

### 1. Add a generic RSS provider over local RSS sources instead of a WeChat-RSS-only provider

The provider should be named around RSS semantics, for example `rss`, and support WeChat RSS SaaS through local source records. A source can be a single aggregate feed named `全部` or category feeds such as `财经` and `科技`. Each source has a display name, source type, feed URL, and provider metadata. The provider parses standard RSS/Atom-like fields and normalizes them into `ProviderArticle`.

Reasoning:
- WeChat RSS SaaS exposes the content as RSS, so a generic provider keeps the boundary stable if the user later changes SaaS vendors.
- The project already has provider abstraction; using another provider avoids contaminating `FetcherService` with feed parsing details.
- This also enables OPML/import workflows later without introducing another provider for every RSS source.
- The user's WeChat RSS setup may expose either one aggregate feed or multiple category feeds, so local sources should model both shapes without changing downstream article import.

Alternative considered:
- Add `wechat-rss` as a hard-coded provider. This is simpler for configuration naming, but it couples the implementation to a paid service where a standard protocol boundary is enough.

### 2. Store one global API key in settings and one or more feed URLs in local source records

The WeChat RSS API key is global and unique, so it belongs in settings or `.env`. RSS feed URLs are user-managed content sources, so they should be stored as local source records rather than `.env` entries. This applies whether the user has one aggregate feed or many category feeds.

Reasoning:
- Secrets should be configured once and redacted consistently.
- RSS feed URLs change with user organization, not deployment environment.
- A database-backed source list supports add/remove/list/health operations and avoids turning `.env` into a subscription database.

Alternative considered:
- Put RSS feed URLs in `.env`. This becomes hard to maintain when feeds are added, renamed, or removed, especially with Chinese source names.

### 3. Keep public accounts as presentation entities, but do not require them to own RSS URLs

RSS sources may include articles from multiple public accounts. With category sources, one public account may appear in multiple categories. With a single aggregate source, all imported articles may simply belong to `全部`. The system should keep `wchat ls` centered on public-account subscriptions by default, while also adding a source/category view.

Reasoning:
- Users still think in terms of public accounts when reviewing local content.
- The same article should be deduplicated by original URL/provider item identity even if it appears in multiple sources.
- Source/category membership is many-to-many and should not be encoded as a single `Feed.category` value.

Alternative considered:
- Treat each RSS source as one subscription and discard public-account identity. This makes source health easy but loses the existing公众号-oriented workflow.

### 4. Use cache-first content import for RSS-backed sources

RSS items may contain summary text or full HTML content. The importer should prefer feed-provided content and only fetch the original article page when the configured content mode allows it.

Suggested modes:
- `feed_only`: never fetch the original article page; import only feed content.
- `prefer_feed`: use feed content when available; fetch original page only when content is missing.
- `fetch_missing`: always try to fill missing content from the original page when possible.

Recommended default for paid WeChat RSS SaaS is `prefer_feed`, with `feed_only` available for users who want zero direct WeChat article requests.

Alternative considered:
- Always fetch the original WeChat article page after discovering items from RSS. This preserves existing parsed-content behavior but does not solve the rate-limit problem.

### 5. Track RSS source health separately from article fetch success

RSS feed retrieval failures, empty feed responses, stale feeds, quota problems, and content import failures should not be collapsed into one generic fetch error. The system should persist enough health state to tell whether the upstream SaaS feed itself is stale or failing.

Reasoning:
- Paid SaaS introduces operational dependencies. Users need to distinguish "no new articles" from "SaaS feed is broken or stale".
- Health status can guide CLI diagnostics and future alerts without changing downstream AI/export behavior.

Alternative considered:
- Only log RSS errors. This is cheaper but loses state across runs and makes batch operations hard to diagnose.

### 6. Make paid-plan quota advisory, not a hard enforcement boundary

The configured SaaS plan limit should warn users when local active RSS sources exceed the paid tier if the user configures such a limit. It should not prevent all fetches by default because provider-side limits may differ from local configuration.

Reasoning:
- The SaaS source is the authority on billing and enforcement.
- Local quota checks are still useful because the user can detect plan mismatch before feed updates fail.

Alternative considered:
- Hard block subscription creation above the configured limit. This is too strict when the user has a custom plan or intentionally keeps inactive feeds locally.

## Risks / Trade-offs

- [RSS feed content may be partial] -> Provide `rss_content_mode` so users can choose between zero direct requests and richer fallback behavior.
- [SaaS pricing or limits can change] -> Store the local quota as user configuration, not as hard-coded plan logic.
- [Feed URLs may contain private tokens even with a global API key] -> Avoid printing full feed URLs in normal CLI output; redact query tokens in diagnostics and logs.
- [Different RSS feeds expose different field names] -> Normalize common RSS/Atom fields and keep raw item metadata for diagnostics.
- [Provider metadata stored as JSON can become hard to query] -> Keep the first version simple, but use a dedicated health table for status and timestamps if diagnostics need filtering.
- [A public account can belong to one aggregate source or multiple RSS categories] -> Model source/category membership separately from the canonical article and public-account records.
- [Existing WeRead subscriptions may remain fragile] -> Keep provider routing per subscription so migrated RSS subscriptions can coexist with old ones during rollout.

## Migration Plan

1. Add RSS provider configuration and parser dependencies using the existing provider factory pattern.
2. Add settings for the global WeChat RSS API key and default fetch/content behavior.
3. Add local RSS source management so users can add either one aggregate feed URL or multiple named category feed URLs.
4. Import RSS source items, infer or reconcile public-account identity, and preserve source/category membership.
5. Add cache-first content import behavior for RSS-backed items.
6. Add RSS source health persistence and CLI diagnostics.
7. Add quota warning based on configured paid-plan limit and active RSS source count.
8. Keep existing subscriptions unchanged; users can migrate selected workflows to RSS sources incrementally.

Rollback strategy:
- Disable RSS sources or switch `article_list_provider` back to the previous provider.
- Keep any new RSS metadata dormant; it does not need to be deleted for WeRead/Wechat2RSS providers to keep working.

## Open Questions

- Should RSS sources be stored in a dedicated `rss_sources` table from the start, or represented as provider-backed feed records with a source type?
- Should OPML import be included in the first implementation or deferred after direct RSS URL subscriptions work?
- Should `feed_only` or `prefer_feed` be the project default when `article_list_provider=rss`?
