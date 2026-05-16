## 1. Attribution Design Grounding

- [x] 1.1 Inspect the current RSS import, feed discovery, subscribe URL resolution, and source membership code paths.
- [x] 1.2 Identify the canonical fields produced by the existing `wchat subscribe <article-url>` flow and document which fields RSS discovery must preserve.
- [x] 1.3 Run GitNexus impact analysis before editing affected symbols and record risk notes for the implementation.

## 2. URL-Based Identity Resolution

- [x] 2.1 Add or refactor an RSS attribution resolver that accepts RSS item metadata and original article URL.
- [x] 2.2 Implement cache-first ownership lookup by existing article URL, provider item identity, stable account identity, and existing local feed metadata.
- [x] 2.3 Add an explicit subscribe-compatible resolver path for unknown public accounts that does not depend on `ARTICLE_LIST_PROVIDER=rss`.
- [x] 2.4 Persist resolved identity metadata so later RSS items from the same public account avoid another subscribe-compatible resolver call.

## 3. RSS Import Integration

- [x] 3.1 Update RSS article import to resolve canonical `Feed` ownership before article persistence.
- [x] 3.2 Ensure auto-created RSS-discovered subscriptions preserve the same identity shape as user-created subscriptions.
- [x] 3.3 Preserve RSS source/category membership independently from canonical feed ownership.
- [x] 3.4 Remove or disable default title/content-derived pseudo feed creation in the RSS import path.
- [x] 3.5 Update RSS-backed fetch flow so `wchat fetch` fetches all active RSS sources by default.
- [x] 3.6 Stop using public-account/date batch completion as the primary RSS-backed fetch progress mechanism.

## 4. CLI Fetch Semantics

- [x] 4.1 Make `wchat fetch` the documented primary command for RSS-backed article acquisition.
- [x] 4.2 Keep `wchat fetch --all` as a compatibility alias or route it to the same RSS-backed behavior.
- [x] 4.3 Remove or deprecate `wchat fetch MP_WXS_xxx` for RSS-backed operation with clear user guidance.
- [x] 4.4 Keep source-specific fetch commands positioned as diagnostics or maintenance commands.

## 5. Failure Policy and Diagnostics

- [x] 5.1 Apply unknown-feed policy when URL-based attribution cannot resolve a public account.
- [x] 5.2 Report cached matches, subscribe-resolved discoveries, skipped items, failed attribution outcomes, and RSS source progress in CLI fetch diagnostics.
- [x] 5.3 Redact RSS feed tokens and API keys from any new diagnostics.

## 6. Repair Existing Incorrect RSS Feeds

- [x] 6.1 Add a dry-run repair path that identifies suspicious RSS pseudo feeds and lists affected articles.
- [x] 6.2 Add a guarded fix path that re-resolves affected article URLs, moves articles to canonical feeds, and preserves source/category membership.
- [x] 6.3 Ensure unresolved repair items are reported without deleting or silently changing data.

## 7. Tests and Verification

- [x] 7.1 Add unit tests for cache-first RSS attribution and subscribe-compatible fallback behavior.
- [x] 7.2 Add tests proving known public accounts do not call the subscribe-compatible resolver per article.
- [x] 7.3 Add tests proving title/content-only hints do not create canonical feeds by default.
- [x] 7.4 Add tests for source/category membership preservation during attribution and repair.
- [x] 7.5 Add CLI tests for `wchat fetch`, `wchat fetch --all`, and deprecated/rejected `wchat fetch MP_WXS_xxx` behavior in RSS mode.
- [x] 7.6 Add tests proving RSS mode does not skip source fetching due to public-account/date batch rows.
- [x] 7.7 Run the relevant test suite and OpenSpec validation before marking implementation complete.
