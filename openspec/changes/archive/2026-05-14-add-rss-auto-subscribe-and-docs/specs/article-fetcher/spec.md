## ADDED Requirements

### Requirement: RSS imports resolve local Feed before article persistence
The article fetch pipeline SHALL resolve or create the owning local `Feed` for each RSS-imported article before inserting the article.

#### Scenario: RSS article belongs to existing feed
- **WHEN** an RSS item identifies a public account that already exists locally
- **THEN** the imported article SHALL use that existing feed as its owner
- **AND** no duplicate feed SHALL be created

#### Scenario: RSS article belongs to discovered feed
- **WHEN** an RSS item identifies a public account that does not exist locally
- **AND** auto-subscribe policy creates a local subscription
- **THEN** the imported article SHALL reference the newly created feed

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

### Requirement: RSS article source membership remains separate from canonical Feed ownership
The article fetch pipeline SHALL preserve RSS source/category membership independently from the canonical public-account feed owner.

#### Scenario: Same account appears in multiple RSS sources
- **WHEN** RSS import processes articles from the same public account across multiple RSS sources
- **THEN** the articles SHALL share the same canonical feed owner when matched
- **AND** source/category memberships SHALL be preserved separately

#### Scenario: Same article appears in multiple RSS sources
- **WHEN** the same article URL appears in multiple RSS sources
- **THEN** the system SHALL keep one canonical article record
- **AND** it SHALL record each source membership without duplicating the article
