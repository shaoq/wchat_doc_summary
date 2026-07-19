## ADDED Requirements

### Requirement: Market data SHALL be fetched through a unified Provider contract

The system SHALL define a `MarketDataProvider` abstraction covering the six market-data categories (indices, volume, statistics, sectors, limit_up, snapshot), returning typed dataclass results that decouple data-source internals from `FinanceClient`.

#### Scenario: Provider returns typed dataclass

- **WHEN** the orchestrator requests a market-data category from a Provider
- **THEN** the Provider SHALL return a typed dataclass result (e.g. `BreadthStatistics`), not a raw dict
- **AND** the orchestrator SHALL convert it into the existing `get_all_market_data()` dict contract unchanged

### Requirement: Provider factory SHALL assemble per-category provider chains

The system SHALL assemble an ordered Provider chain per category from configuration, supporting a primary source plus fallback sources.

#### Scenario: Mixed provider mode assembles fallback chain

- **WHEN** `MARKET_DATA_PROVIDER=mixed` is configured
- **THEN** the factory SHALL place the TickFlow Provider as primary and legacy sources as fallback for each category
- **AND** a failed primary SHALL short-circuit to the next Provider in the chain via the existing `_run_source_strategy` logic

### Requirement: Providers SHALL declare historical-support metadata

Each Provider SHALL declare `supports_historical: bool` metadata so the backfill workflow can decide whether a category is historical-safe under that Provider.

#### Scenario: Historical-only date uses historical-capable provider

- **WHEN** a backfill requests a past trade date for a category
- **AND** the active Provider declares `supports_historical=True`
- **THEN** the system SHALL query that Provider for the historical date
- **AND** a Provider with `supports_historical=False` SHALL be skipped as `skipped_unsupported`
