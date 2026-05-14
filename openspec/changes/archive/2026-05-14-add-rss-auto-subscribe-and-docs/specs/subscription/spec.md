## ADDED Requirements

### Requirement: RSS-discovered public accounts can be auto-subscribed
The subscription system SHALL support automatically creating local public-account subscriptions discovered from RSS items.

#### Scenario: RSS item identifies unknown public account and auto-subscribe is enabled
- **WHEN** RSS import encounters an item whose public account is not present locally
- **AND** `rss_auto_subscribe_discovered_feeds` is enabled
- **THEN** the system SHALL create a local subscription for that public account
- **AND** it SHALL store provider metadata that explains the RSS discovery source

#### Scenario: RSS item identifies existing inactive public account
- **WHEN** RSS import encounters an item whose public account exists locally with inactive status
- **AND** auto-subscribe policy allows activation
- **THEN** the system SHALL reactivate or update the existing subscription instead of creating a duplicate

### Requirement: Discovered subscription default status is configurable
The subscription system SHALL apply the configured default status when creating RSS-discovered subscriptions.

#### Scenario: Discovered feed default status is active
- **WHEN** `rss_discovered_feed_default_status` is `active`
- **AND** RSS import creates a discovered subscription
- **THEN** the new subscription SHALL be active

#### Scenario: Discovered feed default status is inactive
- **WHEN** `rss_discovered_feed_default_status` is `inactive`
- **AND** RSS import creates a discovered subscription
- **THEN** the new subscription SHALL be inactive or pending review according to the local subscription status model

### Requirement: RSS public-account matching prefers stable identifiers
The subscription system SHALL match RSS-discovered public accounts using stable identifiers before falling back to display names.

#### Scenario: RSS item includes provider-side account identity
- **WHEN** an RSS item exposes a provider-side public-account identifier
- **THEN** the system SHALL use that identifier for matching before comparing display names

#### Scenario: RSS item only includes public-account display name
- **WHEN** an RSS item exposes only a public-account display name
- **THEN** the system SHALL normalize that name for matching
- **AND** if no existing subscription matches, it SHALL create a traceable local identifier when auto-subscribe is enabled

### Requirement: RSS-discovered subscriptions are reported to users
The subscription system SHALL expose newly discovered subscriptions in CLI fetch output or diagnostics.

#### Scenario: RSS sync creates new subscriptions
- **WHEN** RSS sync creates one or more local subscriptions
- **THEN** the CLI SHALL report the created public-account names and their default status
- **AND** the subscriptions SHALL appear in subsequent subscription list output
