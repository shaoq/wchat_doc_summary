## ADDED Requirements

### Requirement: RSS feed network failures include diagnostics
The system SHALL surface RSS feed endpoint network failures with actionable, non-empty diagnostics.

#### Scenario: RSS feed request error has an empty message
- **WHEN** `RSSProvider._fetch_feed()` encounters an `httpx.RequestError` whose string message is empty
- **THEN** the raised provider error SHALL include the request exception class name
- **AND** it SHALL include a redacted RSS feed URL when available
- **AND** the outer fetch log SHALL NOT show an empty error summary after the source name

#### Scenario: RSS feed request error has an underlying cause
- **WHEN** an RSS feed request failure includes a lower-level cause
- **THEN** the raised provider error SHALL include the cause class name
- **AND** it SHALL include the cause message when available

#### Scenario: RSS feed URL contains credentials
- **WHEN** an RSS feed request URL contains credential-like query parameters
- **THEN** the diagnostic output SHALL redact those parameter values
- **AND** it SHALL preserve non-sensitive host and path context

### Requirement: RSS feed HTTP status failures include status diagnostics
The system SHALL convert RSS feed HTTP status failures into provider errors with clear status and endpoint context.

#### Scenario: RSS feed endpoint returns an HTTP error
- **WHEN** an RSS feed endpoint responds with an HTTP error status
- **THEN** `RSSProvider._fetch_feed()` SHALL raise `RSSProviderError`
- **AND** the error message SHALL include the HTTP status code
- **AND** the error message SHALL include the redacted feed URL

### Requirement: RSS source failure records are non-empty
The system SHALL store meaningful failure summaries for RSS source fetch failures.

#### Scenario: RSS source request fails before articles are parsed
- **WHEN** `wchat fetch` or `wchat fetch --all` fails while requesting an RSS source feed
- **THEN** the RSS source health failure summary SHALL be non-empty
- **AND** it SHALL include enough diagnostic context to distinguish network request failure from HTTP status failure
