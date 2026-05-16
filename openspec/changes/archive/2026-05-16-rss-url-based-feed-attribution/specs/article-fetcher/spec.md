## MODIFIED Requirements

### Requirement: RSS imports resolve local Feed before article persistence
The article fetch pipeline SHALL resolve or create the owning local `Feed` for each RSS-imported article before inserting the article, using URL-based attribution and cached local identity before creating new subscriptions.

#### Scenario: RSS article belongs to existing feed
- **WHEN** an RSS item identifies a public account that already exists locally
- **THEN** the imported article SHALL use that existing feed as its owner
- **AND** no duplicate feed SHALL be created

#### Scenario: RSS article belongs to discovered feed
- **WHEN** an RSS item identifies a public account that does not exist locally
- **AND** auto-subscribe policy creates a local subscription
- **THEN** the imported article SHALL reference the newly created feed

#### Scenario: RSS article belongs to unknown feed resolved from URL
- **WHEN** an RSS item has a usable original article URL
- **AND** no existing local feed or identity mapping matches the item
- **AND** auto-subscribe policy creates a local subscription
- **THEN** the pipeline SHALL resolve the public account through the subscribe-compatible article URL resolver before inserting the article
- **AND** the imported article SHALL reference the resulting canonical feed

### Requirement: RSS import handles unknown public-account identity according to policy
The article fetch pipeline SHALL handle RSS items whose public-account identity cannot be resolved without corrupting article ownership.

#### Scenario: Unknown identity with auto-subscribe disabled
- **WHEN** RSS import encounters an item with no matching local feed
- **AND** auto-subscribe is disabled
- **THEN** the system SHALL skip, fail, or stage the item according to the configured unknown-feed policy
- **AND** it SHALL NOT insert the article under an unrelated feed

#### Scenario: Unknown identity with placeholder creation allowed
- **WHEN** RSS import encounters an item with insufficient public-account identity
- **AND** placeholder creation is allowed by policy
- **THEN** the system SHALL create a traceable placeholder feed
- **AND** it SHALL preserve raw RSS metadata for later correction

#### Scenario: Unknown identity with only title or content hints
- **WHEN** RSS import encounters an item whose only public-account hints come from the article title, summary, or content body
- **THEN** the system SHALL treat the public-account identity as unresolved unless policy explicitly allows placeholder creation
- **AND** it SHALL NOT create a canonical feed from those hints by default

## ADDED Requirements

### Requirement: RSS-backed fetch progress is source-wide and idempotent
The article fetch pipeline SHALL treat RSS-backed fetching as source-wide idempotent synchronization rather than public-account/date batch traversal.

#### Scenario: RSS fetch runs repeatedly on the same day
- **WHEN** RSS-backed fetching runs multiple times on the same day
- **THEN** the system SHALL fetch active RSS sources according to command policy
- **AND** it SHALL avoid duplicate articles through provider item identity and original URL deduplication
- **AND** it SHALL NOT skip the RSS fetch only because a public-account/date batch row already exists

#### Scenario: RSS fetch records source progress
- **WHEN** an RSS-backed fetch completes for a source
- **THEN** the system SHALL update source health and import diagnostics for that source
- **AND** source progress SHALL be represented independently from public-account/date batch completion

#### Scenario: RSS source appears stale
- **WHEN** an RSS source's newest item is older than the configured stale threshold
- **THEN** the system MAY report the source as stale
- **AND** it SHALL NOT use stale status alone as proof that all public accounts are already fetched for the day
