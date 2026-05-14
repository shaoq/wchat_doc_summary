## ADDED Requirements

### Requirement: Fetch command is the unified RSS acquisition entrypoint
The system SHALL use `wchat fetch` as the primary user-facing command for RSS-backed article acquisition.

#### Scenario: User runs fetch in RSS mode
- **WHEN** the user runs `wchat fetch`
- **AND** the configured article list provider is RSS-backed
- **THEN** the system SHALL fetch all active configured RSS sources
- **AND** it SHALL import new articles through the RSS attribution pipeline

#### Scenario: User runs fetch all in RSS mode
- **WHEN** the user runs `wchat fetch --all`
- **AND** the configured article list provider is RSS-backed
- **THEN** the system SHALL treat the command as equivalent to `wchat fetch`
- **AND** it SHALL not require users to separately run a source-specific fetch command for normal article acquisition

### Requirement: Public-account-specific fetch is not part of RSS-first acquisition
The system SHALL not require or promote `wchat fetch MP_WXS_xxx` for RSS-first article acquisition.

#### Scenario: User passes public account id in RSS mode
- **WHEN** the user runs `wchat fetch <mp-id>`
- **AND** the configured article list provider is RSS-backed
- **THEN** the system SHALL reject the public-account-specific fetch or show a deprecation message
- **AND** it SHALL instruct the user to run `wchat fetch` for unified RSS acquisition

#### Scenario: Fetch help is shown in RSS mode
- **WHEN** the CLI displays fetch help or examples for RSS-backed operation
- **THEN** it SHALL present `wchat fetch` as the normal article acquisition command
- **AND** it SHALL NOT present `wchat fetch MP_WXS_xxx` as the recommended RSS-backed workflow

### Requirement: RSS source fetch remains diagnostic
The system SHALL keep source-specific RSS fetch behavior as a diagnostic or maintenance path rather than the required daily acquisition command.

#### Scenario: User diagnoses RSS source
- **WHEN** the user runs a source-specific fetch or health command
- **THEN** the system MAY fetch or inspect configured RSS sources directly
- **AND** the command output SHALL make clear that normal article acquisition uses `wchat fetch`
