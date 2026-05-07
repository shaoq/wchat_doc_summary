## MODIFIED Requirements

### Requirement: list_subscriptions_for_fetch supports batch-aware filtering

The subscription query used by `fetch_all` SHALL be able to return only the subscriptions that are pending in the current day's batch, while maintaining the existing weight-based sort order.

#### Scenario: Batch mode returns only pending subscriptions sorted by weight
- **WHEN** `fetch_all` queries subscriptions in batch mode
- **THEN** only subscriptions with `status=pending` in today's batch SHALL be returned
- **AND** the result SHALL be sorted by weight DESC, sync_time IS NULL first, name ASC

#### Scenario: Non-batch fetch is unaffected
- **WHEN** `wchat fetch <mp_id>` is invoked for a single subscription
- **THEN** the batch mechanism SHALL NOT be involved
- **AND** the fetch SHALL proceed as before without reading or writing batch records
