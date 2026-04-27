## ADDED Requirements

### Requirement: System shall display grouped news collection summary
The system SHALL present market-summary news collection results as a grouped stage summary instead of scattered standalone lines.

#### Scenario: Show grouped source counts in stable order
- **WHEN** news collection completes during `wchat ai market-summary`
- **THEN** the CLI SHALL display the source summaries for `财联社电报`、`看盘数据`、`相关文章`
- **AND** the three source summaries SHALL appear in a stable order on every run

#### Scenario: Keep empty sources readable
- **WHEN** one or more news sources return no records
- **THEN** the CLI SHALL mark those sources as empty within the grouped summary
- **AND** the output SHALL preserve the same overall structure as non-empty runs

## MODIFIED Requirements

### Requirement: Display time window in CLI output
The system SHALL display source-specific time windows as part of the stage-2 CLI summary when generating market summary.

#### Scenario: Show time windows after news collection
- **WHEN** running `wchat ai market-summary`
- **THEN** after `[2/3] 获取新闻数据` completes, the CLI SHALL display the watch, telegraph, and article windows together as one grouped summary
- **AND** the windows SHALL be shown in a stable source order for every run

#### Scenario: Format time windows as human readable
- **WHEN** displaying time windows in the CLI
- **THEN** the CLI SHALL format each timestamp as `YYYY-MM-DD HH:MM`

#### Scenario: Omit missing windows without breaking layout
- **WHEN** a source does not provide a time window
- **THEN** the CLI SHALL continue rendering the remaining source windows in stable order
- **AND** the CLI SHALL not print placeholder blank lines for the missing source

### Requirement: System shall display staged execution progress
The system SHALL display current market-summary execution progress as three ordered stage blocks with consistent stage conclusions.

#### Scenario: Successful run shows ordered stage blocks
- **WHEN** user executes `wchat ai market-summary` and all stages succeed
- **THEN** the CLI SHALL display `[1/3] 获取市场数据`、`[2/3] 获取新闻数据`、`[3/3] AI 生成市场总结` in that order
- **AND** each started stage SHALL render a compact completion summary before the next stage begins

#### Scenario: Market data failure stops later stage output
- **WHEN** market data is unavailable during stage 1
- **THEN** the CLI SHALL display a failure summary under `[1/3] 获取市场数据`
- **AND** the CLI SHALL stop before rendering stage 2 or stage 3 progress blocks

#### Scenario: Offline run remains clearly labeled
- **WHEN** user executes `wchat ai market-summary --offline`
- **THEN** the execution progress output SHALL clearly indicate that the run is in offline mode

### Requirement: System shall display market data summary
The system SHALL display a compact market data summary immediately after stage 1 completes.

#### Scenario: Show online or cached market data summary
- **WHEN** market data fetch completes with online or cached market data
- **THEN** the CLI SHALL summarize the resolved data source context directly under stage 1
- **AND** the summary SHALL include market snapshot details such as indices,成交概况, and涨跌统计 when available

#### Scenario: Show offline market data summary
- **WHEN** user executes `wchat ai market-summary --offline` and local market data is available
- **THEN** the CLI SHALL display a concise offline-market-data summary instead of realtime market snapshot lines
