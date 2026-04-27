## MODIFIED Requirements

### Requirement: System shall display market data summary (modified)

The system SHALL display a compact market data summary immediately after stage 1 completes, and that summary SHALL reflect both the resolved source strategy outcome and the validated quality state of market breadth data.

#### Scenario: Show validated online or cached market data summary
- **WHEN** market data fetch completes with online or cached market data whose breadth fields are marked `ok`
- **THEN** the CLI SHALL summarize the resolved data source context directly under stage 1
- **AND** the summary SHALL include market snapshot details such as indices, 成交概况, and 涨跌统计
- **AND** breadth items marked `ok` SHALL use explicit success wording such as `已获取`

#### Scenario: Show degraded breadth data summary
- **WHEN** market data fetch completes but成交额 or 涨跌统计 is marked `partial` or `error`
- **THEN** the CLI SHALL display that item as incomplete or failed rather than successful
- **AND** the command SHALL NOT print success wording for degraded zero-value breadth data
- **AND** the user-facing summary SHALL remain meaningful even if other market data items succeeded

#### Scenario: Show offline market data summary
- **WHEN** user executes `wchat ai market-summary --offline` and local market data is available
- **THEN** the CLI SHALL display a concise offline-market-data summary instead of realtime market snapshot lines

#### Scenario: Stable summary under source degradation
- **WHEN** one or more live market data adapters degrade to their declared backup, partial-sample, or empty-value path
- **THEN** the market-summary command SHALL still expose the normalized market data summary contract
- **AND** the command SHALL NOT leak source-specific raw response structures into stage 1 output
