## MODIFIED Requirements

### Requirement: Support force refresh in market-summary CLI

The `market-summary` command SHALL support `--force` flag to bypass cache reads for market data, fetch fresh online data, and overwrite same-trade-date market data cache records safely when caching conditions are met.

#### Scenario: Force refresh market summary with existing market cache
- **WHEN** user runs `wchat ai market-summary --force`
- **AND** the target trade date already has cached market data
- **THEN** system ignores cached market data for reads
- **AND** fetches fresh data from APIs
- **AND** updates same-trade-date market data cache records without database UNIQUE constraint errors
- **AND** continues to later market-summary stages if the refreshed market data is otherwise available

#### Scenario: Force refresh market summary without cache
- **WHEN** user runs `wchat ai market-summary --force`
- **AND** the target trade date has no cached market data
- **THEN** system fetches fresh data from APIs
- **AND** stores the refreshed market data if caching conditions are met
