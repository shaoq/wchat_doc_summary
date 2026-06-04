## ADDED Requirements

### Requirement: Subscriptions store batch export preference
The subscription system SHALL store a per-public-account preference indicating whether the subscription participates in default all-account article export.

#### Scenario: New subscription defaults to included in all export
- **WHEN** a new public-account subscription is created
- **THEN** the subscription SHALL default to participating in `wchat export --all`

#### Scenario: Existing subscriptions default to included after schema compatibility upgrade
- **WHEN** an existing database is opened after the batch export preference is introduced
- **THEN** existing subscription records SHALL default to participating in `wchat export --all`

### Requirement: Subscription CLI displays batch export preference
The subscription CLI SHALL display each public account's batch export preference in list and detail views.

#### Scenario: List subscriptions shows batch export preference
- **WHEN** the user runs `wchat ls`
- **THEN** the subscription table SHALL include a "批量导出" column
- **AND** the column SHALL indicate whether each subscription participates in `wchat export --all`

#### Scenario: Info command shows batch export preference
- **WHEN** the user runs `wchat info <MP_ID>`
- **THEN** the detail panel SHALL include whether the subscription participates in `wchat export --all`

### Requirement: Export CLI can update batch export preference
The export CLI SHALL provide a command to enable or disable a public account's participation in default all-account export.

#### Scenario: Disable subscription from all export
- **WHEN** the user runs `wchat export set-export <MP_ID> false`
- **THEN** the system SHALL store that the subscription does not participate in `wchat export --all`
- **AND** the command SHALL print a clear success message identifying the subscription

#### Scenario: Enable subscription for all export
- **WHEN** the user runs `wchat export set-export <MP_ID> true`
- **THEN** the system SHALL store that the subscription participates in `wchat export --all`
- **AND** the command SHALL print a clear success message identifying the subscription

#### Scenario: Set export preference for unknown subscription
- **WHEN** the user runs `wchat export set-export <MP_ID> false`
- **AND** the subscription does not exist
- **THEN** the command SHALL print a clear not-found message
- **AND** it SHALL NOT create a new subscription
