## ADDED Requirements

### Requirement: System SHALL show real-time progress for batch group updates
The system SHALL show actionable real-time terminal progress while running `wchat ai sector-trends groups update --all`.

#### Scenario: Batch update shows start context
- **WHEN** a user runs `wchat ai sector-trends groups update --all`
- **THEN** the system SHALL display the target trade date, target group count, lookback window, force mode, member refresh mode, and continue-on-error behavior before processing groups

#### Scenario: Batch update shows current group progress
- **WHEN** the batch command starts processing each group
- **THEN** the system SHALL display the current group index, total group count, group name, and current stage

#### Scenario: Batch update shows per-group completion
- **WHEN** a group finishes processing
- **THEN** the system SHALL display that group's final action, member refresh summary, key trend labels when available, output path when available, and elapsed time

#### Scenario: Batch update shows final summary
- **WHEN** the batch command finishes
- **THEN** the system SHALL display success, skipped, failed, member refresh success, member refresh failure, and total elapsed time

### Requirement: System SHALL expose detail levels for group update output
The system SHALL support default, verbose, and quiet terminal output modes for group update commands.

#### Scenario: Default mode is concise but informative
- **WHEN** a user runs `groups update --all` without verbosity flags
- **THEN** the system SHALL show per-group progress and summary information
- **AND** it SHALL NOT print full report content
- **AND** it SHALL NOT print full prompts, headers, or stack traces

#### Scenario: Verbose mode shows detailed diagnostics
- **WHEN** a user runs `groups update --all --verbose`
- **THEN** the system SHALL show member-level refresh actions, skip reasons, retry events, stage timings, and safe API diagnostic metadata when available

#### Scenario: Quiet mode is script friendly
- **WHEN** a user runs `groups update --all --quiet`
- **THEN** the system SHALL suppress live progress details
- **AND** it SHALL still show final counts and failed item summaries when failures occur

### Requirement: System SHALL provide diagnostic API retry messages
The system SHALL include sufficient context when API calls fail and retry during sector or group trend generation.

#### Scenario: Member refresh API retry is contextual
- **WHEN** a member sector trend API call fails and will retry
- **THEN** the system SHALL display the stage, group name, member name, task type, attempt number, maximum attempts, retry delay, and sanitized error message

#### Scenario: Group summary API retry is contextual
- **WHEN** a group trend summary API call fails and will retry
- **THEN** the system SHALL display the stage, group name, task type, attempt number, maximum attempts, retry delay, and sanitized error message

#### Scenario: Verbose API retry shows safe provider metadata
- **WHEN** verbose output is enabled for a retrying API call
- **THEN** the system SHALL include safe provider or model metadata when available
- **AND** it SHALL NOT display API keys, authorization headers, complete request headers, or full prompts

### Requirement: System SHALL provide recovery guidance after group update failures
The system SHALL provide actionable recovery guidance when a batch group update partially or fully fails.

#### Scenario: Member refresh failure suggests retry command
- **WHEN** a member refresh fails after all retry attempts
- **THEN** the final failure detail SHALL include group name, member name, task type, error summary, attempts used, and a suggested retry command

#### Scenario: Group summary failure suggests retry command
- **WHEN** group summary generation fails after all retry attempts
- **THEN** the final failure detail SHALL include group name, task type, error summary, attempts used when available, and a suggested retry command

#### Scenario: Continue-on-error reports partial success
- **WHEN** `continue-on-error` is enabled and one group fails
- **THEN** the system SHALL continue processing remaining groups
- **AND** the final summary SHALL clearly separate successful, skipped, and failed groups

### Requirement: System SHALL emit structured progress events for group updates
The system SHALL expose structured progress events or callbacks from group update services so terminal rendering can be tested and extended without duplicating business logic in the CLI.

#### Scenario: Service emits batch and group events
- **WHEN** batch group update runs with a progress callback
- **THEN** the service SHALL emit events for batch start, group start, stage changes, group completion, group failure, and batch completion

#### Scenario: Service emits member refresh events
- **WHEN** a group update refreshes member sectors
- **THEN** the service SHALL emit events for member refresh start, retry when available, completion, skip, and failure

#### Scenario: Service works without callback
- **WHEN** group update runs without a progress callback
- **THEN** the service SHALL preserve existing return-value behavior
