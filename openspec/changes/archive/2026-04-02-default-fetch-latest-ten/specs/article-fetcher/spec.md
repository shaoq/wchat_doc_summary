## ADDED Requirements

### Requirement: Default fetch mode uses latest article count
The system SHALL treat `wchat fetch` without explicit range options as a "latest articles" synchronization mode. In this mode, each fetch target MUST be limited to the newest 10 articles by default rather than using a default day-based time window.

#### Scenario: Fetch single feed with no explicit range
- **WHEN** the user runs `wchat fetch MP_WXS_xxx` without `--days` and without `--full`
- **THEN** the system fetches at most the newest 10 articles for that feed
- **AND** the CLI output describes the operation as a latest-article sync rather than a recent-days sync

#### Scenario: Fetch all feeds with no explicit range
- **WHEN** the user runs `wchat fetch --all` without `--days` and without `--full`
- **THEN** the system fetches at most the newest 10 articles for each subscribed feed by default

### Requirement: Explicit range options override the default latest mode
The system SHALL preserve explicit range semantics when the user provides `--days` or `--full`. `--full` MUST continue to take precedence over `--days`.

#### Scenario: Days option overrides latest default
- **WHEN** the user runs `wchat fetch MP_WXS_xxx --days 30`
- **THEN** the system performs a time-range fetch for the last 30 days
- **AND** it does not apply the default newest-10 limit

#### Scenario: Full option overrides days option
- **WHEN** the user runs `wchat fetch MP_WXS_xxx --days 30 --full`
- **THEN** the system performs a full-history fetch
- **AND** it does not apply the 30-day window or the default newest-10 limit

### Requirement: Upstream article list failures preserve diagnostic context
When the upstream article list endpoint fails, the system MUST preserve actionable diagnostic context from the upstream response, including the HTTP status code and upstream error message text when available.

#### Scenario: Upstream returns record-specific failure context
- **WHEN** the upstream list request fails with an error body that includes a problematic record identifier or upstream business error code
- **THEN** the system surfaces that identifier or business error code in logs or user-visible error output
- **AND** the final error message is not reduced to only a generic local status such as `API 请求失败: 500`

### Requirement: Default latest-mode fetch is resilient to narrow-window retries
The system SHALL support a bounded narrow-window retry strategy for the default latest-article mode so that an upstream failure in a wider default list window does not immediately prevent synchronization of unaffected recent articles.

#### Scenario: Latest-mode fetch narrows request window after upstream list failure
- **WHEN** the default newest-10 fetch encounters an upstream list failure on its initial list request
- **THEN** the system retries with a smaller list window within a bounded number of attempts
- **AND** if a retry succeeds, the system continues fetching the unaffected recent articles

#### Scenario: Narrow-window retries still fail
- **WHEN** every bounded retry for the default newest-10 mode fails
- **THEN** the system reports the failure with preserved upstream diagnostic context
- **AND** it does not silently mark the fetch as successful
