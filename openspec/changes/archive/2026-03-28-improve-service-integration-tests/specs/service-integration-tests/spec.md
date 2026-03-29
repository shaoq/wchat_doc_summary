## ADDED Requirements

### Requirement: Core services support SQLite-backed integration tests
The system SHALL provide an integration-test path for core services using a real SQLite async database session.

#### Scenario: Service test uses real async session
- **WHEN** a core service integration test runs
- **THEN** the test SHALL use a real SQLite-backed async session instead of a fully mocked session object

### Requirement: Integration-test fixtures manage async resources safely
The system SHALL manage event loops, async sessions, and database engines in test fixtures so that async resources are cleaned up safely.

#### Scenario: Test suite completes without async resource leakage
- **WHEN** the integration test suite finishes
- **THEN** async database resources SHALL be disposed explicitly
- **AND** the test infrastructure SHALL avoid leaving event-loop-close warnings caused by unmanaged async workers

### Requirement: Critical service behaviors are validated through integration tests
The system SHALL cover critical service behaviors with integration tests where ORM, transaction, or session behavior affects correctness.

#### Scenario: Subscription service persistence path
- **WHEN** the subscription service creates or updates a subscription in an integration test
- **THEN** the persisted feed record SHALL be queryable through the real database session

#### Scenario: Market data cache persistence path
- **WHEN** the market data cache service saves and reloads market data in an integration test
- **THEN** the reloaded data SHALL reflect what was persisted through the real ORM path

#### Scenario: Authentication token persistence path
- **WHEN** the authentication service stores a successful login token in an integration test
- **THEN** the token record SHALL be queryable through the real database session
