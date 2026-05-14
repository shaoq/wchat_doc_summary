## Context

The active `integrate-wechat-rss-saas-provider` change introduces RSS SaaS sources as the primary article-list input. In that model, RSS feeds may contain articles from public accounts that have never been manually subscribed in the local database.

The current subscription model assumes local `Feed` rows already exist before articles are fetched for a public account. RSS source import needs a discovery step so newly encountered public accounts become visible in `wchat ls`, article statistics, exports, and market-summary source accounting.

The README also still presents WeRead login as the default first step. That documentation will become misleading once RSS SaaS is the recommended path.

## Goals / Non-Goals

**Goals:**

- Automatically create or reactivate local public-account subscriptions discovered from RSS items when configured to do so.
- Resolve a canonical local `Feed` for each RSS-imported article before article persistence.
- Preserve RSS source/category membership for auto-discovered feeds and articles.
- Provide user-visible reporting for newly discovered public accounts during RSS sync.
- Update README so users understand the RSS SaaS primary workflow, source configuration, automatic discovery, login requirements, and FAQ.

**Non-Goals:**

- Do not implement the base RSS provider or RSS source management primitives; those belong to `integrate-wechat-rss-saas-provider`.
- Do not require RSS feeds to expose perfect public-account metadata.
- Do not remove manual `wchat subscribe` or WeRead/Wechat2RSS compatibility workflows.
- Do not fetch private WeChat account metadata through unauthorized scraping.

## Decisions

### 1. Add an explicit RSS discovery step before article persistence

RSS item processing should extract public-account identity before saving the article. The fetch pipeline should call a subscription discovery helper that returns a local `Feed` row, creating or reactivating one when allowed.

Reasoning:
- `Article.feed_id` is required for correct local grouping.
- Creating the Feed after article insert would require backfill and makes duplicate handling harder.
- A central helper keeps provider parsing, matching, and creation policy consistent.

Alternative considered:
- Store all RSS-imported articles under the RSS source instead of public accounts. This loses the existing公众号-oriented user experience.

### 2. Make auto-subscribe configurable

Add settings such as:

- `rss_auto_subscribe_discovered_feeds`
- `rss_discovered_feed_default_status`

When auto-subscribe is disabled, the system should still avoid corrupt imports: it can skip items without known feeds or route them to an explicit pending/unknown handling path, depending on implementation.

Reasoning:
- Some RSS sources may contain noisy or broad content.
- Users may want newly discovered accounts to be active immediately, inactive pending review, or disabled entirely.

Alternative considered:
- Always auto-create active feeds. This is convenient but can pollute local subscriptions if the RSS source includes unexpected publishers.

### 3. Match public accounts by strongest available identity

Discovery should prefer stable identifiers over display names:

1. provider-side account id or biz-like metadata
2. account/source metadata from RSS item
3. original article URL-derived metadata when available
4. normalized display name
5. generated local placeholder identity when no stronger identifier exists

Reasoning:
- Display names can change or collide.
- RSS feeds vary in metadata quality.
- A generated placeholder is better than dropping articles, but it must remain traceable in provider metadata.

Alternative considered:
- Match only by name. This is simpler but risks merging unrelated accounts with similar names.

### 4. README should document RSS as the recommended path and WeRead as compatibility

README should be updated after the implementation commands and settings are available. It should cover:

- RSS SaaS as the primary workflow.
- Global `WECHAT_RSS_API_KEY` in `.env`.
- RSS URLs managed as local sources, not `.env` entries.
- Single aggregate RSS source and multiple category RSS sources.
- Automatic discovery of public accounts from RSS.
- `wchat ls` default account view and source/category view.
- Login requirements: RSS path does not require `wchat login`; WeRead path still does.
- FAQ for auto-discovery, deduplication, source health, and fallback modes.

Reasoning:
- The usage model changes enough that partial README updates would mislead users.
- Documentation should reflect the final command names and settings from implementation.

## Risks / Trade-offs

- [RSS metadata cannot identify a public account] -> Use a traceable placeholder identity and surface it in diagnostics or skip according to policy.
- [Auto-discovery creates unwanted subscriptions] -> Make auto-subscribe and default discovered status configurable.
- [Name collisions merge unrelated accounts] -> Prefer stable provider metadata and retain raw source metadata for review.
- [README drifts from actual command names] -> Update README after CLI command names are finalized and cover commands with tests or smoke checks where practical.

## Migration Plan

1. Implement discovery settings and subscription matching/creation helper.
2. Integrate discovery into RSS import before article persistence.
3. Add CLI reporting for newly discovered feeds and their default status.
4. Add tests for discovery, matching, disabled auto-subscribe, active/inactive defaults, and article ownership.
5. Update README after command names and settings are implemented.

Rollback strategy:
- Disable `rss_auto_subscribe_discovered_feeds`.
- Existing auto-discovered feeds remain ordinary local `Feed` rows and can be manually disabled or removed using existing subscription management.

## Open Questions

- Should disabled auto-subscribe skip unknown-account articles or create inactive pending feeds?
- What exact placeholder `mp_id` format should be used when only a display name is available?
- Should README include a migration guide from WeRead subscriptions to RSS sources in this change or a separate documentation pass?
