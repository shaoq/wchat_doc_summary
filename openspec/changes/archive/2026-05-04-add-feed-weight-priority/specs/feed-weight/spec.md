## ADDED Requirements

### Requirement: Feed model stores weight
The Feed model SHALL include a `weight` field of type Integer with valid values 0, 5, and 10, where 0 means low priority, 5 means medium (default), and 10 means high priority.

#### Scenario: New subscription defaults to weight 5
- **WHEN** a new Feed is created without specifying weight
- **THEN** the Feed's weight SHALL be 5

#### Scenario: Existing feeds migrated with default weight
- **WHEN** the database migration adds the weight column to existing feeds
- **THEN** all existing feeds SHALL have weight set to 5

### Requirement: Fetch ordering respects weight
The system SHALL provide a method `list_subscriptions_for_fetch()` that returns active subscriptions ordered by weight descending, with tie-breaking by sync status (unsynced first) and name ascending.

#### Scenario: High weight feeds are fetched first
- **WHEN** `fetch --all` is executed with feeds having weights 10, 5, and 0
- **THEN** feeds with weight 10 SHALL be fetched before weight 5
- **AND** feeds with weight 5 SHALL be fetched before weight 0

#### Scenario: Unsynced feeds prioritized within same weight
- **WHEN** two feeds have the same weight and one has never been synced (sync_time IS NULL)
- **THEN** the unsynced feed SHALL appear before the synced feed

#### Scenario: Name ordering for determinism
- **WHEN** two feeds have the same weight and sync status
- **THEN** they SHALL be ordered by name ascending

### Requirement: CLI set-weight command
The system SHALL provide a `wchat sub set-weight <mp_id> <weight>` command that sets the weight of a subscription, where weight MUST be one of 0, 5, or 10.

#### Scenario: Set weight successfully
- **WHEN** user runs `wchat sub set-weight <mp_id> 10`
- **THEN** the feed's weight SHALL be updated to 10
- **AND** the CLI SHALL confirm the change

#### Scenario: Invalid weight value rejected
- **WHEN** user runs `wchat sub set-weight <mp_id> 3`
- **THEN** the CLI SHALL reject the input with an error indicating valid values are 0, 5, or 10

#### Scenario: Non-existent subscription
- **WHEN** user runs `wchat sub set-weight <invalid_mp_id> 10`
- **THEN** the CLI SHALL display an error indicating the subscription was not found
