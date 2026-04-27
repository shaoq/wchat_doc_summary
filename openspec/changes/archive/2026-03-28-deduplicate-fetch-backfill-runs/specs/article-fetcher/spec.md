## ADDED Requirements

### Requirement: Batch fetch performs publish-time backfill at most once per subscription run

The system SHALL avoid running duplicate publish-time backfill work for the same subscription within a single batch fetch execution.

#### Scenario: Single backfill per subscription in batch fetch
- **WHEN** the system executes a batch fetch run across multiple subscriptions
- **THEN** each successfully fetched subscription SHALL trigger publish-time backfill at most once during that batch run
