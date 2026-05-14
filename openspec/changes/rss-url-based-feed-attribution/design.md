## Context

The RSS integration now supports configured WeChat RSS SaaS sources, source health, source/category membership, and auto-subscription for public accounts discovered from RSS imports. The current weak point is attribution: RSS items may not include stable public-account metadata, so fallback behavior can create pseudo feeds from article titles or URL hashes. Those pseudo feeds do not match the identity format created by `wchat subscribe` and can split one public account into many incorrect local subscriptions.

The user can still provide WeChat login credentials when needed, but RSS should remain the primary article-list source. Login-backed resolution should be limited to first discovery of unknown public accounts, not every article import.

The daily user-facing acquisition command should remain `wchat fetch`. RSS source commands are useful for configuration, diagnostics, health checks, and maintenance, but the normal article import flow should not require the user to run a separate `wchat source fetch` command. In RSS-first mode, fetching is source-wide: the system reads configured active RSS sources and then attributes each article to its canonical public account. It is no longer naturally modeled as "fetch this one public account".

## Goals / Non-Goals

**Goals:**

- Attribute each RSS-imported article to the canonical local public-account `Feed` before persistence.
- Use existing article/feed/source mappings first, then cached identities, then subscribe-compatible URL resolution only for unknown public accounts.
- Preserve the same identity shape as existing `wchat subscribe` records when RSS discovers a new public account.
- Avoid title/content-derived public-account creation by default.
- Keep RSS source/category membership independent from canonical feed ownership.
- Make `wchat fetch` the unified daily article acquisition command for RSS-backed fetching.
- Treat `wchat fetch --all` as a compatibility alias when retained.
- Remove or deprecate `wchat fetch MP_WXS_xxx` for RSS-first article acquisition.
- Replace per-public-account/date batch progress in RSS mode with source health, deduplication, and import diagnostics.
- Provide diagnostics and repair support for already-created incorrect RSS pseudo feeds.

**Non-Goals:**

- Replace the WeChat RSS SaaS source or change RSS source/API key configuration.
- Require a subscribe-compatible resolver call for every imported article.
- Use article title prefixes, summaries, or rendered content as authoritative public-account identity.
- Redesign the full subscription database model beyond the mapping metadata needed for attribution.
- Preserve public-account-specific fetch semantics for RSS mode.
- Use trade-day/date batch rows as the main RSS fetch progress mechanism.

## Decisions

### Decision 1: Make attribution URL-first

RSS article attribution SHALL be driven by the original WeChat article URL. The importer should treat RSS metadata as provider item metadata, not as authoritative public-account identity unless the RSS item explicitly exposes a stable account identifier.

Alternatives considered:

- Parse the public account from title/content prefixes. This is rejected because titles are presentation text, can contain unrelated prefixes, and caused incorrect pseudo feeds.
- Trust RSS `author` blindly. This is insufficient because many feed items omit `author`, and display names alone can change or collide.

### Decision 2: Use a tiered resolver

RSS import should resolve ownership in tiers:

```text
RSS item original_url
  ↓
existing article by original_url/provider item id?
  ↓
existing identity mapping such as __biz/provider_feed_id/mp_id?
  ↓
existing canonical Feed match?
  ↓
subscribe-compatible resolver for unknown public account only
  ↓
configured failure policy
```

Every article gets a lightweight ownership check, but the expensive subscribe-compatible resolver is only invoked when the public account is unknown locally.

### Decision 3: Resolve unknown accounts through a subscribe-compatible path

When auto-subscribe is enabled and an RSS item belongs to an unknown public account, the system should invoke a resolver equivalent to the existing `wchat subscribe <article-url>` behavior. This resolver must be selected explicitly and must not depend on the global article-list provider being `rss`, because RSSProvider itself is not capable of resolving public-account identity from a WeChat article URL.

The resolved subscription should preserve canonical fields such as `mp_id`, display name, avatar/cover metadata, provider name, and provider-side identifiers when available. RSS-specific discovery metadata should be appended without overwriting the canonical identity.

### Decision 4: Cache successful attribution

The first successful URL resolution should create or update local identity metadata so later articles from the same public account can be attributed without another login-backed resolver call. Candidate keys include `__biz`, provider-side feed identity, canonical `mp_id`, normalized display name with supporting metadata, and source membership records.

### Decision 5: Make failure behavior explicit

If URL-based attribution cannot identify a public account, the importer should follow a configured unknown-feed policy. The safe default should avoid creating one pseudo feed per article. Valid outcomes are:

- `skip`: do not persist the article until ownership can be resolved.
- `pending`: stage/report the item for review if the project has or adds a pending model.
- `placeholder`: create an inactive traceable placeholder only when explicitly enabled.

### Decision 6: Keep `wchat fetch` as the unified command

RSS-backed acquisition should be reached through the existing fetch command:

```text
wchat fetch
  ↓
load active RSS sources
  ↓
fetch each source
  ↓
deduplicate articles by provider item identity and original URL
  ↓
attribute each new item to canonical Feed
  ↓
persist source health, source membership, and import diagnostics
```

`wchat fetch --all` can remain as a compatibility alias, but the preferred command should be `wchat fetch`. `wchat source fetch` should remain a diagnostic or maintenance command for checking source connectivity and source-specific behavior.

`wchat fetch MP_WXS_xxx` should be removed or deprecated for the RSS-first workflow because RSS sources are aggregate/category feeds. A public account becomes an attribution result, not the unit of upstream fetching.

### Decision 7: RSS progress is source-wide and idempotent

RSS mode should not use `fetch_batches(mp_id, batch_date)` as the primary progress model. That table is shaped for public-account/date batch traversal, while RSS mode repeatedly pulls upstream source snapshots.

RSS progress should instead rely on:

- provider item identity and original URL deduplication;
- per-source success, failure, empty, and stale health state;
- import diagnostics for created, matched, skipped, and failed items;
- source/category membership records.

Date or newest-item timestamps may still support stale-source diagnostics, but they should not decide whether a whole RSS fetch is skipped for the day.

## Risks / Trade-offs

- [Risk] Subscribe-compatible URL resolution may require WeChat login and can still be rate-limited. → Mitigation: invoke it only for first-time unknown public accounts, cache results, and report failures without blocking known-account imports.
- [Risk] Some article URLs may not expose enough stable identity for cached matching. → Mitigation: fall back to explicit subscribe-compatible resolution and store all available identity metadata after success.
- [Risk] Display-name matching can merge unrelated accounts. → Mitigation: use display names only as a low-confidence fallback with supporting metadata, and prefer stable identifiers.
- [Risk] Existing incorrect pseudo feeds already pollute local data. → Mitigation: provide a repair step that re-resolves articles by original URL, moves articles to canonical feeds, and removes empty pseudo feeds only after verification.
- [Risk] Calling the existing subscription path from RSS import can accidentally use `ARTICLE_LIST_PROVIDER=rss`. → Mitigation: introduce an explicit resolver abstraction or explicit provider selection for article URL identity resolution.
- [Risk] Removing public-account-specific fetch may break users or scripts calling `wchat fetch MP_WXS_xxx`. → Mitigation: deprecate with a clear message first, or keep the argument rejected with guidance to use `wchat fetch`.
- [Risk] Without date batch skipping, users may worry repeated fetches duplicate data. → Mitigation: make deduplication and source health diagnostics visible in fetch output.

## Migration Plan

1. Add URL-based attribution logic behind the RSS import path.
2. Add or reuse identity metadata storage so a resolved public account can be matched by stable keys on later imports.
3. Change RSS auto-subscribe creation to use subscribe-compatible URL resolution for unknown public accounts.
4. Update CLI diagnostics to report resolved, cached, skipped, and failed attribution outcomes.
5. Update `wchat fetch` to route RSS mode through active RSS sources by default.
6. Deprecate or remove `wchat fetch MP_WXS_xxx` in RSS mode, and update help text/documentation.
7. Stop using public-account/date batch progress as the primary RSS mode progress mechanism.
8. Add a repair/maintenance path for existing RSS pseudo feeds:
   - identify suspicious feeds created from RSS URL hashes or title-derived names;
   - re-resolve their articles by original URL;
   - update `articles.feed_id` to canonical feeds when resolution succeeds;
   - preserve source/category membership;
   - delete or deactivate empty pseudo feeds after review.

Rollback is straightforward for new imports by disabling URL-based auto-discovery or setting unknown-feed policy to `skip`. Data migration should be run separately and should support dry-run output before mutating existing article ownership.

## Open Questions

- Should the repair path be a dedicated CLI command, or part of a diagnostics command with an explicit `--fix` flag?
- Should the default failure policy be `skip` or `pending` if no pending-review model exists yet?
- Which canonical identity fields from the current subscribe resolver are guaranteed available across providers and should become required for RSS attribution caching?
- Should `wchat fetch MP_WXS_xxx` be removed immediately, or kept for one release as a deprecation warning?
