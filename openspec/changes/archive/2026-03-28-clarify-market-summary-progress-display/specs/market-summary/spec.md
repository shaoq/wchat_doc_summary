## ADDED Requirements

### Requirement: System shall display execution context before stages

The system SHALL display a short execution context block before stage execution begins so the user can immediately understand what run is being performed.

#### Scenario: Display trade date and execution mode
- **WHEN** user executes `wchat ai market-summary`
- **THEN** the command SHALL display the resolved trade date before the first stage
- **AND** the command SHALL display the execution mode, such as online, offline, or force refresh

#### Scenario: Display market data strategy
- **WHEN** stage execution is about to begin
- **THEN** the command SHALL display the market data strategy for this run
- **AND** the strategy text SHALL make clear whether the command will prefer cache, use local-only data, or bypass cache reads and refresh data

## MODIFIED Requirements

### Requirement: System shall display staged execution progress

The system SHALL display current stage progress as persistent stage blocks during market-summary command execution. Each stage block SHALL retain its title in the final transcript and SHALL use labels that match the actual work being performed.

#### Scenario: Display stage 1/3
- **WHEN** starting to fetch market data
- **THEN** display a persistent stage block titled "[1/3] 获取市场数据"

#### Scenario: Display stage 2/3
- **WHEN** starting to aggregate telegraphs, watch items, and articles
- **THEN** display a persistent stage block titled "[2/3] 获取新闻数据"

#### Scenario: Display stage 3/3
- **WHEN** starting AI generation and result persistence
- **THEN** display a persistent stage block titled "[3/3] 生成并保存市场总结"

### Requirement: System shall display market data summary

The system SHALL display a structured summary after market data fetch completes, including both result data and the source semantics for that stage.

#### Scenario: Display index summary
- **WHEN** market data fetch completes
- **THEN** display main indices' closing price and change percentage

#### Scenario: Display volume and change summary
- **WHEN** market data fetch completes
- **THEN** display trading volume and gain/loss counts

#### Scenario: Display market data source
- **WHEN** market data fetch completes successfully
- **THEN** display the market data source for that stage, such as API, cache, or offline/local data

#### Scenario: Offline mode data summary
- **WHEN** using --offline mode
- **THEN** display "离线模式: 无实时数据" or equivalent offline market-data wording inside the stage 1 block

### Requirement: System shall display article statistics

The system SHALL display a structured news-input summary after related news fetch completes.

#### Scenario: Display input counts
- **WHEN** news fetch completes
- **THEN** display the number of telegraphs, watch items, and articles gathered for this run

#### Scenario: Display source status
- **WHEN** news fetch completes
- **THEN** display source status indicators for telegraphs, watch items, and articles

#### Scenario: Display time windows
- **WHEN** news fetch completes
- **THEN** display the watch, telegraph, and article time windows in a stable order

#### Scenario: Prompt when all sources are empty
- **WHEN** no telegraphs, watch items, or articles are available
- **THEN** the stage 2 block SHALL still retain the same structure and explicitly show zero counts

### Requirement: System shall display AI generation duration

The system SHALL display the execution duration and completion state for the final generation-and-save stage.

#### Scenario: Display duration
- **WHEN** AI generation and save complete
- **THEN** display the duration for the AI generation portion

#### Scenario: Display saved output path
- **WHEN** the summary has been persisted successfully
- **THEN** the final stage block SHALL display the output file path as part of the completed state

### Requirement: System shall indicate offline mode

The system SHALL use prominent visual indicators in offline mode and SHALL make the offline semantics understandable from the transcript alone.

#### Scenario: Offline mode indicator
- **WHEN** executing command with --offline parameter
- **THEN** display a visible offline-mode label in the execution context or stage 1 block
- **AND** the output SHALL make clear that no realtime market fetch is being performed
