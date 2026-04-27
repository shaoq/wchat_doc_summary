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
