## MODIFIED Requirements

### Requirement: Subscriptions preserve provider identity
The subscription system SHALL store provider identity and provider-side feed metadata for each subscribed public account so that article synchronization can be routed through the correct provider. The subscription system SHALL also store a weight field to control fetch ordering priority.

#### Scenario: Create subscription through provider-backed resolution
- **WHEN** the system resolves a public account through a provider-aware subscription flow
- **THEN** the resulting subscription stores the provider name
- **AND** it stores the provider-side feed identifier or equivalent metadata when available
- **AND** the subscription weight defaults to 5

### Requirement: Subscribe flow remains URL-based for users
The subscription experience SHALL continue to support subscribing from an article URL even when the underlying resolution implementation is no longer WeRead-specific.

#### Scenario: Subscribe from article URL with provider-aware resolver
- **WHEN** the user runs `wchat subscribe <article-url>`
- **THEN** the system resolves the target public account through the configured resolver/provider path
- **AND** the created subscription remains usable by subsequent `fetch` operations

## ADDED Requirements

### Requirement: Subscription list displays weight column
The `wchat sub ls` command SHALL display a weight column in the subscription table showing each feed's priority level.

#### Scenario: List subscriptions shows weight
- **WHEN** user runs `wchat sub ls`
- **THEN** the table SHALL include a "权重" column displaying the feed's weight value (0/5/10)

### Requirement: Subscription info displays weight
The `wchat sub info <mp_id>` command SHALL display the feed's weight in the detail panel.

#### Scenario: Info command shows weight
- **WHEN** user runs `wchat sub info <mp_id>`
- **THEN** the detail panel SHALL include the feed's weight value
