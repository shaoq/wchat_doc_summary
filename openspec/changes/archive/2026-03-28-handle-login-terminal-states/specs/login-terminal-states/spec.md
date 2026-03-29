## ADDED Requirements

### Requirement: Login CLI stops immediately on terminal failure states

The system SHALL stop login polling immediately when the login service reports an expired QR code or an unrecoverable error.

#### Scenario: QR code expired
- **WHEN** the login polling loop receives status `expired`
- **THEN** the CLI stops polling immediately
- **AND** the user sees a QR-code-expired message

#### Scenario: Login error
- **WHEN** the login polling loop receives status `error`
- **THEN** the CLI stops polling immediately
- **AND** the user sees the reported error message

### Requirement: Login CLI continues polling for waiting states

The system SHALL continue polling while the login service reports waiting-like intermediate states.

#### Scenario: Waiting for scan or confirmation
- **WHEN** the login polling loop receives status `waiting`, `pending`, or `scanned`
- **THEN** the CLI continues polling until a terminal state or timeout is reached
