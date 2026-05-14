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

### Requirement: Generic RSS article list provider
The system SHALL support a generic RSS article-list provider that can fetch configured RSS source URLs and normalize feed items into provider article items.

#### Scenario: Fetch articles from RSS source URL
- **WHEN** an RSS source is fetched
- **THEN** the system SHALL request that source's configured RSS feed URL
- **AND** it SHALL normalize each feed item into the internal provider article structure

#### Scenario: Fetch articles from single aggregate RSS source
- **WHEN** only one RSS source named `全部` or equivalent is configured
- **THEN** the system SHALL fetch that source as the complete upstream article list
- **AND** it SHALL NOT require any category-specific source to exist

#### Scenario: Normalize RSS item identity and URL
- **WHEN** an RSS item contains a GUID, id, or link
- **THEN** the provider article SHALL preserve a stable provider item identity when available
- **AND** it SHALL preserve the item link as the original article URL when available

#### Scenario: Normalize RSS content fields
- **WHEN** an RSS item contains title, publish time, summary, or HTML content fields
- **THEN** the provider article SHALL expose those fields to the fetch pipeline
- **AND** downstream import logic SHALL be able to use the feed-provided HTML content without another provider call

### Requirement: RSS provider fetches per configured source
The system SHALL route RSS-backed fetching through locally configured source URLs while using the single global WeChat RSS API key from settings when authentication is required.

#### Scenario: Multiple RSS sources use different feed URLs
- **WHEN** two active RSS sources have different feed URLs
- **THEN** fetching each source SHALL request its own feed URL
- **AND** article items from one source SHALL preserve that source membership

#### Scenario: Global API key is applied to RSS source fetch
- **WHEN** an RSS category source requires the WeChat RSS API key
- **THEN** the provider SHALL obtain the key from settings
- **AND** individual RSS category source records SHALL NOT store the API key value

### Requirement: RSS provider redacts sensitive feed URLs in diagnostics
The system SHALL avoid exposing private RSS feed query tokens in normal diagnostic output.

#### Scenario: Feed URL contains token query parameter
- **WHEN** the system logs or displays an RSS feed URL containing query parameters
- **THEN** sensitive query values SHALL be redacted from normal output
- **AND** the unredacted URL SHALL remain available only in persisted provider metadata needed for fetching

