## ADDED Requirements

### Requirement: Export command supports all active public accounts
`wchat export` SHALL support exporting articles for all active public accounts through an explicit `--all` option.

#### Scenario: Export all active public accounts
- **WHEN** the user runs `wchat export --all`
- **THEN** the system SHALL export articles for every active public account
- **AND** each public account SHALL use its own existing export directory under `output/export_articles/<mp_id>/`
- **AND** each article SHALL be exported using the HTML export format

#### Scenario: Export all with force rebuild
- **WHEN** the user runs `wchat export --all --force`
- **THEN** the system SHALL rebuild each exported public account's output directory before writing that account's HTML files
- **AND** it SHALL NOT delete the `output/export_articles` root as a single bulk operation

#### Scenario: Export command requires one scope
- **WHEN** the user runs `wchat export` without an `MP_ID` and without `--all`
- **THEN** the command SHALL fail with a clear usage message

#### Scenario: Export command rejects conflicting scopes
- **WHEN** the user runs `wchat export <mp_id> --all`
- **THEN** the command SHALL fail with a clear usage message
- **AND** it SHALL NOT export articles

#### Scenario: No active public accounts exist
- **WHEN** the user runs `wchat export --all`
- **AND** there are no active public accounts
- **THEN** the command SHALL print a clear no-subscriptions message
- **AND** it SHALL exit without creating article files

### Requirement: Export output clearly reports scope, mode, and destination
The export command SHALL print terminal output that makes the export scope, mode, format, and destination clear before or during work.

#### Scenario: Single public account export starts
- **WHEN** the user runs `wchat export <mp_id>`
- **THEN** the command output SHALL identify the public account name when available
- **AND** it SHALL show the public account `mp_id`
- **AND** it SHALL show that the mode is incremental
- **AND** it SHALL show that the format is HTML
- **AND** it SHALL show the output directory

#### Scenario: Forced single public account export starts
- **WHEN** the user runs `wchat export <mp_id> --force`
- **THEN** the command output SHALL identify the mode as force rebuild
- **AND** it SHALL indicate that the account export directory is rebuilt

#### Scenario: All public accounts export starts
- **WHEN** the user runs `wchat export --all`
- **THEN** the command output SHALL show the number of public accounts to export
- **AND** it SHALL show that the mode is incremental
- **AND** it SHALL show that the format is HTML

### Requirement: Export output reports per-account and aggregate results
The export command SHALL report exported, skipped, failed, and total article counts in a way that is clear for both single-account and all-account exports.

#### Scenario: Single public account export completes
- **WHEN** single-account export completes
- **THEN** the command output SHALL show the number of newly exported articles
- **AND** it SHALL show the number of existing skipped articles
- **AND** it SHALL show the number of failed articles
- **AND** it SHALL show the total number of articles considered

#### Scenario: Single public account has no new exported articles
- **WHEN** single-account incremental export completes with zero newly exported articles
- **AND** at least one article was skipped because the HTML file already exists
- **THEN** the command output SHALL clearly state that there were no new articles to export

#### Scenario: All public accounts export reports each account
- **WHEN** `wchat export --all` processes public accounts
- **THEN** the command output SHALL include a per-account progress marker such as `[current/total]`
- **AND** each account summary SHALL include exported, skipped, failed, and total counts

#### Scenario: All public accounts export completes
- **WHEN** `wchat export --all` completes
- **THEN** the command output SHALL show aggregate account count
- **AND** it SHALL show aggregate exported, skipped, failed, and article total counts

### Requirement: Export continues after per-article failures
The export command SHALL record per-article write failures and continue processing remaining articles where possible.

#### Scenario: One article file fails to write
- **WHEN** writing an article HTML file fails during export
- **THEN** the command SHALL log a concise warning identifying the affected article
- **AND** it SHALL increment the failed count
- **AND** it SHALL continue exporting remaining articles in the same public account where possible

#### Scenario: One public account fails during all export
- **WHEN** one public account cannot be exported during `wchat export --all`
- **THEN** the command SHALL report that account failure
- **AND** it SHALL continue processing remaining public accounts where possible
- **AND** the final aggregate summary SHALL include the failure count
