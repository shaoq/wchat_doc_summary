## ADDED Requirements

### Requirement: All-account export respects subscription batch export preference
`wchat export --all` SHALL export only active public accounts whose subscription batch export preference is enabled.

#### Scenario: All export includes enabled active subscriptions
- **WHEN** the user runs `wchat export --all`
- **AND** an active subscription participates in all export
- **THEN** the system SHALL export articles for that subscription using the existing HTML export behavior

#### Scenario: All export skips disabled active subscriptions
- **WHEN** the user runs `wchat export --all`
- **AND** an active subscription does not participate in all export
- **THEN** the system SHALL NOT export articles for that subscription
- **AND** the skipped subscription SHALL NOT contribute to the exported public-account count

#### Scenario: Force all export still respects preference
- **WHEN** the user runs `wchat export --all --force`
- **AND** an active subscription does not participate in all export
- **THEN** the system SHALL NOT rebuild that subscription's export directory
- **AND** it SHALL NOT export articles for that subscription

#### Scenario: No subscriptions enabled for all export
- **WHEN** the user runs `wchat export --all`
- **AND** active subscriptions exist
- **AND** none of them participate in all export
- **THEN** the command SHALL print a clear message that no subscriptions are enabled for batch export
- **AND** it SHALL exit without creating article files

### Requirement: Explicit single-account export ignores batch export preference
`wchat export <MP_ID>` SHALL remain an explicit export operation and SHALL NOT be blocked by the subscription batch export preference.

#### Scenario: Explicit export of disabled subscription
- **WHEN** the user runs `wchat export <MP_ID>`
- **AND** the subscription does not participate in `wchat export --all`
- **THEN** the system SHALL still export articles for that subscription using the existing HTML export behavior

#### Scenario: Explicit forced export of disabled subscription
- **WHEN** the user runs `wchat export <MP_ID> --force`
- **AND** the subscription does not participate in `wchat export --all`
- **THEN** the system SHALL still rebuild that subscription's export directory
- **AND** it SHALL export articles for that subscription using the existing HTML export behavior
