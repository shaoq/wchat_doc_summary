## ADDED Requirements

### Requirement: RSS source health is tracked per source
The system SHALL track health state for each RSS-backed source.

#### Scenario: Record successful RSS source check
- **WHEN** an RSS source is fetched successfully
- **THEN** the system SHALL record `last_success_at`
- **AND** it SHALL clear or reduce consecutive failure state for that source

#### Scenario: Record failed RSS source check
- **WHEN** an RSS source fetch fails due to HTTP, timeout, or parse errors
- **THEN** the system SHALL record the failure time and error summary
- **AND** it SHALL increment consecutive failure state for that source

#### Scenario: Record empty RSS source response
- **WHEN** an RSS source fetch succeeds but returns no article items
- **THEN** the system SHALL record an empty response occurrence
- **AND** it SHALL distinguish empty responses from transport or parse failures

### Requirement: Stale RSS sources are detectable
The system SHALL identify RSS sources whose newest feed item has not changed within a configured stale threshold.

#### Scenario: Feed newest item is older than stale threshold
- **WHEN** the newest known item from an RSS source is older than the configured stale threshold
- **THEN** the system SHALL mark or report that source as stale
- **AND** the stale state SHALL be visible through diagnostics

#### Scenario: Feed has recent item
- **WHEN** an RSS source contains an item newer than the configured stale threshold
- **THEN** the system SHALL NOT report that source as stale

### Requirement: Paid RSS plan quota warning is reported
The system SHALL warn when active RSS sources exceed the configured paid SaaS plan limit.

#### Scenario: Active RSS source count exceeds configured limit
- **WHEN** the number of active RSS sources is greater than `wechat_rss_plan_limit`
- **THEN** the system SHALL report a quota warning
- **AND** the warning SHALL include active count and configured limit

#### Scenario: Active RSS source count is within configured limit
- **WHEN** the number of active RSS sources is less than or equal to `wechat_rss_plan_limit`
- **THEN** the system SHALL NOT report a quota warning

### Requirement: RSS source diagnostics redact secrets
RSS source health diagnostics SHALL redact secrets from feed URLs and stored error output.

#### Scenario: Diagnostic output includes feed source
- **WHEN** diagnostics display an RSS feed URL or source identifier
- **THEN** query-token values and other configured secret parameters SHALL be redacted
- **AND** the output SHALL remain useful for identifying the affected subscription
