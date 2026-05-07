## MODIFIED Requirements

### Requirement: fetch_all uses batch-based progress tracking

The `FetcherService.fetch_all` method SHALL use the `fetch_batches` table to determine which subscriptions to process, instead of iterating through the full subscription list from the beginning every time.

#### Scenario: First run creates batch and processes all subscriptions
- **WHEN** `fetch_all` is called and no batch exists for today
- **THEN** it SHALL create pending batch records for all active subscriptions
- **AND** it SHALL process subscriptions in weight-descending order
- **AND** each completed subscription SHALL be marked `done` in the batch

#### Scenario: Resumed run only processes pending subscriptions
- **WHEN** `fetch_all` is called and batch records exist for today with mixed statuses
- **THEN** it SHALL only process subscriptions with `status=pending`
- **AND** it SHALL skip subscriptions with `status=done`
- **AND** pending subscriptions SHALL be processed in weight-descending order

#### Scenario: Rate limit interrupts batch and leaves remaining as pending
- **WHEN** a `RateLimitError` occurs during batch processing
- **THEN** the current subscription SHALL remain `pending`
- **AND** the batch loop SHALL break
- **AND** remaining subscriptions SHALL stay `pending` for the next run
