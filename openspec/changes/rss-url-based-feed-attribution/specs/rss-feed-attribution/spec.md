## ADDED Requirements

### Requirement: RSS article attribution is URL-based
The system SHALL attribute RSS-imported articles to canonical public-account feeds by using the original WeChat article URL as the primary ownership input.

#### Scenario: RSS item provides original article URL
- **WHEN** RSS import processes an item with an original WeChat article URL
- **THEN** the system SHALL use that URL to determine the owning public account
- **AND** it SHALL NOT derive the owning public account from the article title or content body by default

#### Scenario: RSS item lacks original article URL
- **WHEN** RSS import processes an item without a usable original article URL
- **THEN** the system SHALL handle the item according to the configured unknown-feed policy
- **AND** it SHALL NOT create an article-title-derived public-account subscription by default

### Requirement: RSS attribution uses cached identity before subscription resolution
The system SHALL avoid invoking subscribe-compatible public-account resolution when a local article, feed, or identity mapping already determines ownership.

#### Scenario: Existing article is found by URL
- **WHEN** RSS import encounters an item whose original URL matches an existing article
- **THEN** the system SHALL use the existing article's canonical feed owner
- **AND** it SHALL NOT invoke subscribe-compatible public-account resolution for that item

#### Scenario: Existing identity mapping is found
- **WHEN** RSS import extracts or looks up a stable account identity that maps to an existing feed
- **THEN** the imported article SHALL use that existing feed as owner
- **AND** the system SHALL NOT invoke subscribe-compatible public-account resolution for that item

### Requirement: Unknown RSS public accounts use subscribe-compatible resolution
The system SHALL resolve unknown RSS public accounts from the original article URL using a resolver compatible with the existing URL-based subscribe flow when auto-subscribe is enabled.

#### Scenario: Unknown public account is resolved from article URL
- **WHEN** RSS import encounters an item with a usable original article URL
- **AND** no existing local feed or identity mapping matches the item
- **AND** RSS auto-subscribe is enabled
- **THEN** the system SHALL invoke subscribe-compatible public-account resolution for that article URL
- **AND** the created or matched subscription SHALL preserve the canonical identity shape used by user-initiated subscriptions

#### Scenario: Subscribe-compatible resolution succeeds once for a public account
- **WHEN** subscribe-compatible resolution identifies a public account for an RSS item
- **THEN** the system SHALL persist identity metadata that allows later RSS items from the same public account to match locally
- **AND** later matching items SHALL NOT require another subscribe-compatible resolution call

### Requirement: RSS attribution reports resolution outcomes
The system SHALL report RSS attribution outcomes so users can understand which articles were matched, discovered, skipped, or failed.

#### Scenario: RSS import discovers a public account
- **WHEN** RSS import creates or reuses a subscription through subscribe-compatible resolution
- **THEN** the CLI diagnostics SHALL report the public account name and whether it was created or matched

#### Scenario: RSS import cannot resolve ownership
- **WHEN** RSS import cannot determine the owning public account for an RSS item
- **THEN** the CLI diagnostics SHALL report the item as skipped, pending, or failed according to policy
- **AND** the diagnostics SHALL include enough non-secret context to identify the affected RSS item

### Requirement: RSS pseudo-feed repair is supported
The system SHALL provide a controlled way to repair existing incorrectly attributed RSS pseudo feeds by re-resolving their articles from original URLs.

#### Scenario: Repair moves article to canonical feed
- **WHEN** a repair operation re-resolves an article currently owned by an RSS pseudo feed
- **AND** the original article URL resolves to a canonical public account
- **THEN** the system SHALL update the article to reference the canonical feed
- **AND** it SHALL preserve RSS source/category membership

#### Scenario: Repair cannot resolve pseudo feed article
- **WHEN** a repair operation cannot resolve an article currently owned by an RSS pseudo feed
- **THEN** the system SHALL leave the article ownership unchanged or mark it for review according to repair policy
- **AND** it SHALL report the unresolved article without deleting data silently
