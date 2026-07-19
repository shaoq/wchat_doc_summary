## ADDED Requirements

### Requirement: TickFlow-backed indices and sectors SHALL be historical-safe

When the TickFlow Provider is active and its tier supports historical queries, the `indices` and `sectors` categories SHALL be treated as historical-safe, expanding backfill coverage beyond `volume` and `limit_up`.

#### Scenario: Indices backfilled for a past trade date

- **WHEN** backfill runs for a past trade date
- **AND** the TickFlow Provider is active with `supports_historical=True` for indices
- **THEN** backfill SHALL fetch indices for that date from TickFlow
- **AND** it SHALL write the cache rows under that trade date

#### Scenario: Tier too low keeps category skipped

- **WHEN** the TickFlow key tier lacks historical capability for a category
- **THEN** backfill SHALL report that category as `skipped_unsupported`
- **AND** it SHALL NOT write rows from a realtime-only source for a historical date
