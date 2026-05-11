## ADDED Requirements

### Requirement: Batch progress uses effective trade day

`FetcherService.fetch_all()` SHALL track batch progress by effective A-share trade day rather than by calendar day. The effective fetch trade day SHALL be the latest A-share trade day for the current Shanghai-local time, with the trade-day boundary at 09:15.

#### Scenario: Weekend rerun keeps previous trade-day batch
- **WHEN** `fetch_all()` is invoked on a weekend
- **THEN** the system SHALL use the latest previous A-share trade day as the batch date
- **AND** subscriptions already marked `done` for that trade day SHALL be skipped

#### Scenario: Holiday rerun keeps previous trade-day batch
- **WHEN** `fetch_all()` is invoked on a non-weekend exchange holiday
- **THEN** the system SHALL use the latest previous A-share trade day as the batch date
- **AND** it SHALL NOT create a fresh batch only because the calendar date changed

#### Scenario: Trade day before 09:15 uses previous trade-day batch
- **WHEN** `fetch_all()` is invoked on an A-share trade day before 09:15 local time
- **THEN** the system SHALL use the previous A-share trade day as the batch date
- **AND** completed subscriptions from that previous trade-day batch SHALL remain skipped

#### Scenario: Trade day at or after 09:15 uses current trade-day batch
- **WHEN** `fetch_all()` is invoked on an A-share trade day at or after 09:15 local time
- **THEN** the system SHALL use the current A-share trade day as the batch date
- **AND** it SHALL create or resume batch progress for that trade day

### Requirement: Batch operations consistently use the effective trade day

All `fetch_all()` batch operations SHALL use the same effective trade-day value within one invocation, including batch creation, pending-feed lookup, done marking, cleanup cutoff calculation, and force reset.

#### Scenario: Successful feed is marked done for effective trade day
- **WHEN** a feed is successfully fetched during `fetch_all()`
- **THEN** the system SHALL mark that feed `done` for the effective trade-day batch
- **AND** it SHALL NOT mark a calendar-day batch for a different date

#### Scenario: Force resets effective trade-day batch
- **WHEN** `wchat fetch --all --force` is invoked
- **THEN** the system SHALL delete batch records for the effective trade day
- **AND** it SHALL create fresh `pending` records for active subscriptions under that same effective trade day

#### Scenario: Completion message identifies effective trade day
- **WHEN** all subscriptions for the effective trade-day batch are already `done`
- **THEN** the CLI SHALL report completion for that trade day
- **AND** the message SHALL NOT imply that the batch is tied to the current calendar day

### Requirement: Existing batch schema remains compatible

The system SHALL continue using the existing `fetch_batches.batch_date` column and `(mp_id, batch_date)` uniqueness constraint, while interpreting `batch_date` as the effective fetch trade date for new batch records.

#### Scenario: New records store effective trade date
- **WHEN** the system creates `fetch_batches` records after this change
- **THEN** each record's `batch_date` SHALL equal the effective fetch trade date
- **AND** the record SHALL remain unique by `mp_id` and `batch_date`

#### Scenario: Old batch rows are not migrated
- **WHEN** old `fetch_batches` rows exist from calendar-day behavior
- **THEN** the system SHALL NOT require a database migration before running `fetch_all()`
- **AND** normal retention cleanup SHALL eventually remove stale rows
