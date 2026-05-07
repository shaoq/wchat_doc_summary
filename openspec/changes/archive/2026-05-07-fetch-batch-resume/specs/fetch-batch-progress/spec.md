## ADDED Requirements

### Requirement: Batch progress is tracked per subscription per day

The system SHALL maintain a `fetch_batches` table that records the fetch status of each active subscription for each day. Each record SHALL contain `mp_id`, `batch_date` (calendar date), and `status` ("pending" or "done"). The combination of `mp_id` and `batch_date` SHALL be unique.

#### Scenario: First run of the day creates pending records for all active subscriptions
- **WHEN** `fetch --all` is invoked and no batch records exist for today's date
- **THEN** the system SHALL insert one `pending` record per active subscription
- **AND** each record SHALL have `batch_date` set to today's calendar date

#### Scenario: Subscription added mid-day is automatically included
- **WHEN** a new subscription is created after a batch has already started for today
- **AND** `fetch --all` is invoked again
- **THEN** the system SHALL insert a `pending` record for the new subscription
- **AND** existing batch records SHALL remain unchanged

#### Scenario: Cancelled subscription is excluded from batch processing
- **WHEN** a subscription has been deactivated (status=0)
- **AND** batch records exist for that subscription
- **THEN** the system SHALL NOT include that subscription in the fetch queue
- **AND** the existing batch record SHALL remain but be ignored

### Requirement: Completed subscriptions are skipped on same-day re-run

The system SHALL skip subscriptions marked as `done` when resuming a batch within the same day.

#### Scenario: Re-run skips already completed subscriptions
- **WHEN** `fetch --all` is invoked and some subscriptions have `status=done` for today
- **THEN** the system SHALL only process subscriptions with `status=pending`
- **AND** it SHALL skip all `done` subscriptions without making API calls

#### Scenario: All subscriptions completed shows completion message
- **WHEN** `fetch --all` is invoked and all subscriptions have `status=done` for today
- **THEN** the system SHALL display a message indicating all subscriptions are already synced
- **AND** it SHALL NOT make any API calls

### Requirement: Batch resets automatically on a new day

The system SHALL create a new batch when `batch_date` changes to a new calendar date. Previous day's batch records SHALL NOT affect the new day's fetch behavior.

#### Scenario: Next day starts fresh batch
- **WHEN** `fetch --all` is invoked on a new calendar date
- **THEN** the system SHALL create new `pending` records for all active subscriptions
- **AND** previous day's batch records SHALL NOT influence the ordering or selection

#### Scenario: Pending records from previous day are not resumed
- **WHEN** some subscriptions were left `pending` from yesterday
- **AND** `fetch --all` is invoked today
- **THEN** the system SHALL create a fresh batch for today
- **AND** yesterday's `pending` records SHALL NOT be processed

### Requirement: Rate-limited feed stays pending for retry

When a `RateLimitError` interrupts the batch, the current subscription SHALL remain in `pending` status so it is retried on the next run.

#### Scenario: Rate limit preserves current feed as pending
- **WHEN** a `RateLimitError` occurs while fetching subscription C
- **THEN** subscription C SHALL remain `pending`
- **AND** subsequent subscriptions D, E, F SHALL also remain `pending`
- **AND** on the next `fetch --all` invocation, subscriptions C, D, E, F SHALL be processed

### Requirement: Force flag creates a fresh batch

The `--force` CLI option SHALL clear today's batch and create a new one, allowing a complete re-fetch.

#### Scenario: Force flag resets today's batch
- **WHEN** `fetch --all --force` is invoked
- **THEN** the system SHALL delete all batch records for today
- **AND** it SHALL create new `pending` records for all active subscriptions
- **AND** all subscriptions SHALL be fetched from scratch

### Requirement: Old batch records are cleaned up automatically

The system SHALL delete batch records older than 7 days at the start of each `fetch --all` run.

#### Scenario: Cleanup removes records older than 7 days
- **WHEN** `fetch --all` is invoked
- **THEN** the system SHALL delete all `fetch_batches` records where `batch_date` is more than 7 days ago
- **AND** this cleanup SHALL happen before batch creation or resumption logic
