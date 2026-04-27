## ADDED Requirements

### Requirement: WeRead client uses a unified request path
The system SHALL route all WeRead proxy API calls through a unified client request path with consistent timeout, retry, header, and error-handling behavior.

#### Scenario: Login result request uses unified request path
- **WHEN** the system queries a WeRead login result
- **THEN** the client SHALL use the same request infrastructure used by other WeRead API methods
- **AND** the request SHALL honor the configured timeout, retry count, and authorization header rules

### Requirement: WeRead login result is normalized for callers
The system SHALL return a normalized login-result payload for authentication flows.

#### Scenario: Successful login result
- **WHEN** the upstream login-result response contains a valid token
- **THEN** the client SHALL return a payload containing `status`, `message`, `token`, and `user_info`
- **AND** the `status` value SHALL indicate a successful login state

#### Scenario: Waiting login result
- **WHEN** the upstream login-result response indicates that scanning or confirmation is still pending
- **THEN** the client SHALL return a payload containing a waiting-like `status`
- **AND** the payload SHALL still follow the same normalized key structure

#### Scenario: Expired login result
- **WHEN** the upstream login-result response indicates the QR code has expired
- **THEN** the client SHALL return a payload containing an expired `status`
- **AND** the payload SHALL include a human-readable `message`

### Requirement: WeRead client exposes normalized metadata payloads
The system SHALL normalize known field-name differences in WeRead metadata responses before returning them to callers.

#### Scenario: Normalize公众号信息 response
- **WHEN** the client receives a公众号信息 response with alias field names
- **THEN** it SHALL return a normalized payload containing `mp_id`, `name`, `intro`, and `cover` when available

#### Scenario: Normalize article list response
- **WHEN** the client receives an article-list response
- **THEN** it SHALL return a payload whose consumers can consistently read article items and paging metadata without depending on upstream field aliases

### Requirement: WeRead client reports transport errors consistently
The system SHALL surface network and unrecoverable HTTP failures through a consistent client error contract.

#### Scenario: Network request failure
- **WHEN** a WeRead API request fails after exhausting retries due to a transport error
- **THEN** the client SHALL raise a `WeReadAPIError`

#### Scenario: Unrecoverable HTTP failure
- **WHEN** a WeRead API request returns an unrecoverable HTTP error after retries
- **THEN** the client SHALL raise a `WeReadAPIError`
