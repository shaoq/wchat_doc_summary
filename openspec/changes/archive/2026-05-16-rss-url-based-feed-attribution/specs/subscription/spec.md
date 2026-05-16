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
