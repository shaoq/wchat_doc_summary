## ADDED Requirements

### Requirement: Network request errors include actionable diagnostics
The system SHALL log network-layer request failures with enough diagnostic context to identify the failure class and target request without exposing sensitive values.

#### Scenario: Request error has an empty message
- **WHEN** an `httpx.RequestError` is raised and its string message is empty
- **THEN** the retry log SHALL include the exception class name
- **AND** the retry log SHALL include a redacted request URL when the request is available
- **AND** the retry log SHALL NOT end with only an empty error message

#### Scenario: Request error has an underlying cause
- **WHEN** an `httpx.RequestError` includes a lower-level cause
- **THEN** the diagnostic output SHALL include the cause class name
- **AND** it SHALL include the cause message when available

#### Scenario: Request URL contains sensitive query parameters
- **WHEN** a failed request URL contains sensitive query parameters such as `key`, `k`, `token`, or `access_token`
- **THEN** the diagnostic output SHALL redact those parameter values
- **AND** it SHALL preserve non-sensitive host and path context needed for troubleshooting

### Requirement: Token expiry remains distinct from request errors
The system SHALL preserve existing token-expiry detection and SHALL NOT classify HTTP token expiry responses as network request errors.

#### Scenario: WeRead token expiry response is returned
- **WHEN** a WeRead HTTP response body contains `WeReadError401`
- **THEN** the system SHALL raise `AuthExpiredError`
- **AND** it SHALL NOT retry the request as a generic network error
- **AND** the visible diagnostic SHALL remain distinguishable from `httpx.RequestError` diagnostics

### Requirement: Retry overrides apply to request-error exhaustion
The system SHALL use the effective retry count for both HTTP status failures and network request failures.

#### Scenario: Request error occurs with retry override disabled
- **WHEN** `WeReadClient._request()` is called with `max_retries_override=0`
- **AND** an `httpx.RequestError` occurs
- **THEN** the system SHALL raise `WeReadAPIError` after the first failed attempt
- **AND** it SHALL NOT continue retrying based on the client's default retry count

#### Scenario: Request error occurs with a custom retry override
- **WHEN** `WeReadClient._request()` is called with a positive `max_retries_override`
- **AND** every attempt raises `httpx.RequestError`
- **THEN** the system SHALL stop after the override-defined number of retries is exhausted
- **AND** the raised error SHALL include the enhanced request-error diagnostic
