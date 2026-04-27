## MODIFIED Requirements

### Requirement: System shall display market data summary (modified)

The system SHALL display a compact market data summary immediately after stage 1 completes, and that summary SHALL reflect the resolved source strategy outcome rather than an implicit implementation detail.

#### Scenario: Show online or cached market data summary
- **WHEN** market data fetch completes with online or cached market data
- **THEN** the CLI SHALL summarize the resolved data source context directly under stage 1
- **AND** the summary SHALL include market snapshot details such as indices, 成交概况, and 涨跌统计 when available
- **AND** the source context SHALL remain meaningful even if different market data types were produced by different adapters under the declared strategy

#### Scenario: Show offline market data summary
- **WHEN** user executes `wchat ai market-summary --offline` and local market data is available
- **THEN** the CLI SHALL display a concise offline-market-data summary instead of realtime market snapshot lines

#### Scenario: Stable summary under source degradation
- **WHEN** one or more live market data adapters degrade to their declared backup or empty-value path
- **THEN** the market-summary command SHALL still expose the normalized market data summary contract
- **AND** the command SHALL NOT leak source-specific raw response structures into stage 1 output

#### Scenario: Expose free-priority breadth source outcome
- **WHEN** volume and rise-fall statistics resolve through the free-priority primary source, the legacy fallback chain, or the empty-value degraded path
- **THEN** the stage 1 output SHALL clearly reflect the breadth-data source outcome
- **AND** users SHALL be able to distinguish primary free-source success, legacy fallback success, and degraded empty-value failure
