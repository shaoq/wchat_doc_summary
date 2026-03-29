## ADDED Requirements

### Requirement: Missing article publish times can be backfilled safely
The system SHALL provide a publish-time backfill capability for articles that already exist in the database but have no `publish_time`.

#### Scenario: Backfill missing publish time for a subscription
- **WHEN** the system runs publish-time backfill for a subscription identified by `mp_id`
- **THEN** it SHALL find articles under that subscription whose `publish_time` is missing
- **AND** it SHALL attempt to resolve publish times from the upstream article list data

### Requirement: Backfill uses subscription identifier semantics consistently
The system SHALL use the subscription `mp_id` as the external identifier for publish-time backfill operations.

#### Scenario: Backfill called from fetch workflow
- **WHEN** publish-time backfill is invoked from the article fetch workflow
- **THEN** the workflow SHALL pass the subscription `mp_id`
- **AND** the backfill implementation SHALL resolve the corresponding feed internally

### Requirement: Backfill failures do not invalidate successful article fetching
The system SHALL treat publish-time backfill as a best-effort post-processing step.

#### Scenario: Backfill partially fails
- **WHEN** some articles fail to resolve publish times during backfill
- **THEN** the system SHALL keep already fetched articles persisted
- **AND** it SHALL report the backfill failure through logging without marking the main fetch as failed
