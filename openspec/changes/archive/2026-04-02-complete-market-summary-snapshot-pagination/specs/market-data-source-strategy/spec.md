## MODIFIED Requirements

### Requirement: Volume and rise-fall statistics share one market snapshot strategy

The system SHALL compute trading volume and rise-fall statistics from a shared validated full-market snapshot whenever the primary realtime snapshot source can provide a complete market sample, and the pagination logic SHALL adapt to the upstream's actual page size rather than a fixed local page cap.

#### Scenario: Shared realtime snapshot succeeds with adaptive pagination
- **WHEN** the primary full-market snapshot source reports a market `total` larger than the first page record count
- **AND** the upstream actually returns fewer rows per page than the requested `pz`
- **THEN** the system SHALL continue fetching the remaining pages based on the first page's actual record count
- **AND** the system SHALL compute both volume and rise-fall statistics from the completed shared snapshot
- **AND** the two outputs SHALL correspond to the same fetch moment

#### Scenario: Shared realtime snapshot uses unique-record completeness
- **WHEN** the system aggregates multiple snapshot pages
- **THEN** completeness SHALL be evaluated using unique stock records rather than raw appended row count
- **AND** duplicate records across pages SHALL NOT cause the system to mark the snapshot complete too early

#### Scenario: Shared realtime snapshot remains incomplete after pagination attempt
- **WHEN** the primary full-market snapshot source still returns too few unique records after the system attempts the required pages
- **THEN** the system SHALL treat that snapshot as incomplete
- **AND** the system SHALL NOT treat the derived volume and rise-fall statistics as successful full-market breadth data
- **AND** the system SHALL attempt the declared fallback source before returning a degraded result
