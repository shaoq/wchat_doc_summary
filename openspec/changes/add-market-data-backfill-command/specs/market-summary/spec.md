## ADDED Requirements

### Requirement: Historical market-summary SHALL remain cache-replay only
The system SHALL keep historical `market-summary` generation separate from market-data backfill so summary generation remains reproducible from local cache.

#### Scenario: Historical summary with cache uses cached data
- **WHEN** a user runs `wchat ai market-summary --date 2026-05-15`
- **AND** local market-data cache exists for `2026-05-15`
- **THEN** the command SHALL use the cached market data
- **AND** it SHALL NOT invoke market-data backfill automatically

#### Scenario: Historical summary without cache points to backfill workflow
- **WHEN** a user runs `wchat ai market-summary --date 2026-05-15`
- **AND** local market-data cache is missing for `2026-05-15`
- **THEN** the command SHALL stop before summary generation
- **AND** it SHALL communicate that historical market data must be populated through `wchat ai market-data backfill --date 2026-05-15`

#### Scenario: Force does not bypass historical replay rule
- **WHEN** a user runs `wchat ai market-summary --date 2026-05-15 --force`
- **AND** `2026-05-15` is a historical trade date with no market-data cache
- **THEN** the command SHALL NOT fetch realtime replacement market data
- **AND** it SHALL preserve the historical cache-only behavior
