## 1. Settings And Policy

- [x] 1.1 Add settings for RSS auto-subscribe enablement and discovered-feed default status.
- [x] 1.2 Define unknown public-account handling policy for disabled auto-subscribe and insufficient identity cases.
- [x] 1.3 Add validation for allowed discovered-feed default statuses.

## 2. Subscription Discovery

- [x] 2.1 Implement RSS public-account identity extraction from provider item metadata, author/source fields, and original URL metadata when available.
- [x] 2.2 Implement subscription matching that prefers stable provider identifiers before normalized display names.
- [x] 2.3 Implement auto-create/reactivate helper for RSS-discovered public-account feeds.
- [x] 2.4 Preserve RSS discovery metadata on auto-created feeds for diagnostics and later correction.
- [x] 2.5 Report newly discovered feeds and their default status in RSS sync or fetch output.

## 3. Fetch Pipeline Integration

- [x] 3.1 Resolve or create the canonical local Feed before saving each RSS-imported article.
- [x] 3.2 Ensure articles from known feeds reuse existing Feed rows and do not create duplicates.
- [x] 3.3 Handle unknown public-account identity according to configured policy without assigning articles to unrelated feeds.
- [x] 3.4 Preserve RSS source/category membership separately from canonical Feed ownership.
- [x] 3.5 Keep existing article deduplication by provider item identity and original URL intact across auto-discovered feeds.

## 4. README Documentation

- [x] 4.1 Update README overview and feature list to present RSS SaaS as the recommended article sync path.
- [x] 4.2 Update README configuration section for `WECHAT_RSS_API_KEY`, RSS content mode, auto-subscribe settings, and login requirements.
- [x] 4.3 Document that RSS feed URLs are managed as local RSS sources rather than `.env` entries.
- [x] 4.4 Document single aggregate RSS source mode and multiple category RSS source mode.
- [x] 4.5 Document RSS auto-discovered subscriptions, default status behavior, and why discovered accounts appear in `wchat ls`.
- [x] 4.6 Document `wchat ls` public-account view and RSS source/category view.
- [x] 4.7 Update FAQ for RSS auth, API key placement, source URL management, auto-subscribe, deduplication, and source health.

## 5. Tests And Verification

- [x] 5.1 Add subscription discovery tests for stable identifier matching, normalized-name fallback, reactivation, and duplicate avoidance.
- [x] 5.2 Add fetcher tests for RSS article ownership resolution before persistence.
- [x] 5.3 Add tests for auto-subscribe enabled, disabled, active default, inactive default, and unknown-identity policy.
- [x] 5.4 Add tests for source/category membership preservation when accounts or articles appear in multiple RSS sources.
- [x] 5.5 Review README command examples against the implemented CLI names.
- [x] 5.6 Run relevant tests and `openspec validate add-rss-auto-subscribe-and-docs --strict`.
