## ADDED Requirements

### Requirement: RSS attribution propagates AuthExpiredError
The system SHALL propagate `AuthExpiredError` from the RSS URL attribution path instead of silently swallowing it.

#### Scenario: WeRead Token expires during Tier 4 attribution
- **WHEN** `RSSAttributionService._subscribe_compatible_resolve()` calls the WeRead API and receives an HTTP 401
- **THEN** `AuthExpiredError` SHALL be re-raised
- **AND** it SHALL NOT be caught by the generic `except Exception` handler
- **AND** the error SHALL propagate to the caller of `attribute()`

#### Scenario: Non-auth attribution failures remain unchanged
- **WHEN** the RSS URL attribution fails for a non-auth reason (network error, parsing error, etc.)
- **THEN** the system SHALL return `None` and log a warning as before
- **AND** the article SHALL be marked as failed without interrupting other articles

### Requirement: RSS source fetch aborts on AuthExpiredError
The system SHALL abort RSS source processing immediately when `AuthExpiredError` is detected in the article processing loop.

#### Scenario: AuthExpiredError during article processing
- **WHEN** `_fetch_rss_source()` encounters `AuthExpiredError` while processing an article's attribution
- **THEN** the article loop SHALL stop immediately
- **AND** the `AuthExpiredError` SHALL propagate to `fetch_from_rss_sources()`
- **AND** previously processed articles in the same source SHALL be preserved

#### Scenario: AuthExpiredError does not affect articles before the error
- **WHEN** an RSS source has processed 5 articles successfully and the 6th triggers `AuthExpiredError`
- **THEN** the 5 successfully processed articles SHALL be preserved in the database
- **AND** the source health SHALL NOT be updated to success (partial processing)

### Requirement: RSS fetch session terminates on AuthExpiredError
The system SHALL terminate the entire RSS fetch session (all remaining sources) when `AuthExpiredError` is detected.

#### Scenario: AuthExpiredError stops remaining source processing
- **WHEN** `fetch_from_rss_sources()` catches `AuthExpiredError` from any source
- **THEN** the source loop SHALL break immediately
- **AND** the failed source SHALL be recorded with a failure summary mentioning Token expiration
- **AND** remaining sources SHALL NOT be processed
- **AND** the user-facing output SHALL indicate Token expiration as the termination reason

#### Scenario: Non-auth errors continue to next source
- **WHEN** a non-auth exception occurs during RSS source processing
- **THEN** the system SHALL record the failure and continue processing remaining sources
- **AND** the behavior SHALL be identical to the current implementation
