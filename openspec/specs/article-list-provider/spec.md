## ADDED Requirements

### Requirement: System supports pluggable article list providers
The system SHALL define a provider abstraction for fetching article lists so that article discovery is not bound to a single upstream implementation. Each provider MUST return article items in a normalized internal structure.

#### Scenario: Fetch article list through configured provider
- **WHEN** the system is configured to use a specific article list provider
- **THEN** article discovery uses that provider instead of a hard-coded upstream endpoint
- **AND** the provider returns normalized article items consumable by the fetch pipeline

### Requirement: Wechat2RSS provider is supported as an article list source
The system SHALL support `Wechat2RSS` as an article list provider for subscribed public accounts.

#### Scenario: Query article list from Wechat2RSS
- **WHEN** the configured provider is `Wechat2RSS`
- **THEN** the system can query the provider for a subscribed public account's recent articles
- **AND** the returned items include enough information to continue article import, including article URL and title

### Requirement: Provider article items preserve source metadata
The system SHALL preserve provider-specific metadata for imported article items, including provider name and provider-side item identity when available.

#### Scenario: Import provider item with external identity
- **WHEN** a provider returns an article item with an external item identifier
- **THEN** the system stores or propagates that identifier together with the provider name
- **AND** downstream import logic can use it for diagnostics or deduplication
