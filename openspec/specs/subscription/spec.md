## ADDED Requirements

### Requirement: Subscriptions preserve provider identity
The subscription system SHALL store provider identity and provider-side feed metadata for each subscribed public account so that article synchronization can be routed through the correct provider.

#### Scenario: Create subscription through provider-backed resolution
- **WHEN** the system resolves a public account through a provider-aware subscription flow
- **THEN** the resulting subscription stores the provider name
- **AND** it stores the provider-side feed identifier or equivalent metadata when available

### Requirement: Subscribe flow remains URL-based for users
The subscription experience SHALL continue to support subscribing from an article URL even when the underlying resolution implementation is no longer WeRead-specific.

#### Scenario: Subscribe from article URL with provider-aware resolver
- **WHEN** the user runs `wchat subscribe <article-url>`
- **THEN** the system resolves the target public account through the configured resolver/provider path
- **AND** the created subscription remains usable by subsequent `fetch` operations

### Requirement: RSS sources can be configured
The subscription system SHALL allow users to configure one or more named RSS sources from paid WeChat RSS SaaS feed URLs.

#### Scenario: Add single aggregate RSS source
- **WHEN** the user adds one RSS source with a name such as `全部` and an RSS feed URL
- **THEN** the system SHALL persist the source name, provider identity, and feed URL
- **AND** future RSS fetches SHALL be able to use it as the complete aggregate upstream source

#### Scenario: Add RSS category source
- **WHEN** the user adds an RSS source with a category name and RSS feed URL
- **THEN** the system SHALL persist the source name, provider identity, and feed URL
- **AND** future RSS fetches SHALL preserve the source/category membership for imported items

#### Scenario: Global API key is not stored in RSS source
- **WHEN** the user adds an RSS source
- **THEN** the system SHALL NOT store the WeChat RSS API key in the source record
- **AND** fetch operations SHALL use the global API key from settings when needed

### Requirement: RSS source records preserve SaaS provider metadata
The subscription system SHALL preserve provider metadata needed to operate paid WeChat RSS SaaS sources.

#### Scenario: Store SaaS metadata for RSS source
- **WHEN** an RSS source is created with provider-side metadata
- **THEN** the system SHALL persist the provider name, provider source identifier when available, and provider metadata
- **AND** subsequent fetch operations SHALL be able to resolve the feed URL from the stored source data

### Requirement: Active RSS sources can be counted for plan checks
The subscription system SHALL expose the active RSS source count needed by paid-plan quota diagnostics.

#### Scenario: Count active RSS sources
- **WHEN** the system evaluates the configured WeChat RSS SaaS plan limit
- **THEN** it SHALL count active RSS sources
- **AND** inactive or non-RSS sources SHALL NOT count against that local RSS plan warning

### Requirement: Public accounts can belong to one or more RSS sources
The subscription system SHALL preserve membership between public accounts or imported articles and RSS sources.

#### Scenario: Public account appears in single aggregate source
- **WHEN** articles from a public account appear in the aggregate RSS source only
- **THEN** the system SHALL associate that public account and imported articles with the aggregate source
- **AND** it SHALL NOT require a more specific category to be available

#### Scenario: Public account appears in multiple category sources
- **WHEN** articles from the same public account appear in two RSS category sources
- **THEN** the system SHALL preserve both category memberships
- **AND** `wchat ls` SHALL be able to display that public account under or with both categories

#### Scenario: Same article appears in multiple category sources
- **WHEN** the same article URL appears in more than one RSS category source
- **THEN** the system SHALL store one canonical article record
- **AND** it SHALL preserve membership for each source/category where the article appeared

### Requirement: Subscription listing supports source views
The subscription list command SHALL support both public-account-oriented and source-oriented views for RSS-backed content.

#### Scenario: List public accounts with categories
- **WHEN** the user runs the default subscription list command
- **THEN** RSS-backed public accounts SHALL remain visible as public-account rows when they can be inferred
- **AND** rows SHALL display associated RSS source names when available

#### Scenario: List by RSS source
- **WHEN** the user requests a source view
- **THEN** the system SHALL group RSS-backed content by configured RSS source
- **AND** each group SHALL show source health and associated public accounts or article counts when available

<!-- delta from add-rss-auto-subscribe-and-docs, updated by rss-url-based-feed-attribution -->
## MODIFIED Requirements

### Requirement: RSS-discovered public accounts can be auto-subscribed
The subscription system SHALL support automatically creating local public-account subscriptions discovered from RSS items, and RSS-discovered subscriptions SHALL use subscribe-compatible article URL resolution when the public account is unknown locally.

#### Scenario: RSS item identifies unknown public account and auto-subscribe is enabled
- **WHEN** RSS import encounters an item whose public account is not present locally
- **AND** `rss_auto_subscribe_discovered_feeds` is enabled
- **AND** the item has a usable original article URL
- **THEN** the system SHALL resolve the public account through the subscribe-compatible article URL resolver
- **AND** it SHALL create a local subscription for that public account using the same canonical identity shape as `wchat subscribe`
- **AND** it SHALL store provider metadata that explains the RSS discovery source

#### Scenario: RSS item identifies existing inactive public account
- **WHEN** RSS import encounters an item whose public account exists locally with inactive status
- **AND** auto-subscribe policy allows activation
- **THEN** the system SHALL reactivate or update the existing subscription instead of creating a duplicate

### Requirement: RSS public-account matching prefers stable identifiers
The subscription system SHALL match RSS-discovered public accounts using stable identifiers and cached URL-derived identity before falling back to display names.

#### Scenario: RSS item includes provider-side account identity
- **WHEN** an RSS item exposes a provider-side public-account identifier
- **THEN** the system SHALL use that identifier for matching before comparing display names

#### Scenario: RSS item can be matched through URL-derived identity
- **WHEN** an RSS item has an original article URL whose stable account identity is already cached locally
- **THEN** the system SHALL match the RSS item to the existing local subscription for that identity
- **AND** it SHALL NOT invoke subscribe-compatible article URL resolution for that item

#### Scenario: RSS item only includes public-account display name
- **WHEN** an RSS item exposes only a public-account display name
- **THEN** the system SHALL normalize that name for matching only after stable identity matching fails
- **AND** if no existing subscription matches, it SHALL use subscribe-compatible article URL resolution when a usable original article URL is available and auto-subscribe is enabled
- **AND** it SHALL NOT create a title-derived or content-derived local identifier by default

### Requirement: RSS-discovered subscriptions are reported to users
The subscription system SHALL expose newly discovered subscriptions in CLI fetch output or diagnostics.

#### Scenario: RSS sync creates new subscriptions
- **WHEN** RSS sync creates one or more local subscriptions
- **THEN** the CLI SHALL report the created public-account names and their default status
- **AND** the subscriptions SHALL appear in subsequent subscription list output
