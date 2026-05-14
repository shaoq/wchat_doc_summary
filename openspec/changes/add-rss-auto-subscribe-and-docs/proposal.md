## Why

The RSS SaaS integration can return articles from public accounts that do not yet exist in the local subscription table. If those accounts are not auto-created, `wchat ls`, per-account statistics, and downstream workflows will be incomplete even though articles were imported successfully.

The README also still documents the older WeRead-first workflow. Once RSS SaaS becomes the primary path, the project documentation must clearly explain RSS configuration, global API key usage, aggregate/category sources, auto-discovered subscriptions, and when login is still required.

## What Changes

- Add RSS-driven public-account discovery: when an RSS item identifies a public account that does not exist locally, the system creates or stages a local subscription automatically.
- Add configuration for auto-discovered subscription behavior, including whether auto-subscribe is enabled and the default status for discovered feeds.
- Ensure RSS article import resolves a canonical local `Feed` before article persistence, so imported articles remain grouped by public account.
- Preserve RSS source/category membership for auto-discovered feeds and duplicate RSS appearances without duplicating articles.
- Update README to document the RSS SaaS primary workflow, global API key placement, local RSS source management, aggregate/category modes, auto-discovery behavior, login requirements, and FAQ.
- Preserve existing manual subscribe, WeRead, and Wechat2RSS workflows as compatibility paths.

## Capabilities

### New Capabilities
- `project-documentation`: Documents user-facing setup and workflows, including README behavior for RSS SaaS usage.

### Modified Capabilities
- `subscription`: Add RSS-driven automatic public-account subscription discovery and default status behavior.
- `article-fetcher`: Resolve or create the owning local Feed for RSS-imported articles before persistence.

## Impact

- Affected code areas:
  - RSS provider item normalization and public-account metadata extraction
  - Subscription service creation/update paths
  - Fetcher RSS article import and deduplication flow
  - CLI output for newly discovered subscriptions
  - Settings for auto-subscribe and discovered-feed default status
  - README usage documentation
- Data impact:
  - Auto-discovered feeds must have stable local identifiers and provider metadata.
  - Imported articles must reference the correct local Feed even when the Feed did not exist before the RSS sync.
  - Source/category membership must survive when one account or article appears in multiple RSS sources.
- External systems:
  - This change assumes the RSS SaaS provider supplies enough metadata, such as author/source fields or article URLs, to infer public-account identity when possible.
