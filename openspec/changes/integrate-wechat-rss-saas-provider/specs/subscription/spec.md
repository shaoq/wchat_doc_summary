## ADDED Requirements

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
