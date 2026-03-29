## ADDED Requirements

### Requirement: CLI commands are registered from domain modules
The system SHALL support registering CLI commands from domain-specific command modules while keeping a unified root entry point.

#### Scenario: Root CLI entry point remains available
- **WHEN** the user runs `python -m src.cli --help`
- **THEN** the system SHALL load a unified root CLI entry point
- **AND** that entry point SHALL register commands supplied by domain command modules

### Requirement: Existing command names remain stable after modularization
The system SHALL preserve existing user-facing command names and subcommand names when moving command definitions into modules.

#### Scenario: Top-level commands remain unchanged
- **WHEN** the CLI is reorganized into modules
- **THEN** the existing top-level commands SHALL remain available under the same names

#### Scenario: AI subcommands remain unchanged
- **WHEN** the user runs `python -m src.cli ai --help`
- **THEN** the existing AI subcommands SHALL remain available under the same names

### Requirement: Command modularization does not require a new invocation method
The system SHALL preserve the current CLI invocation entry points after modularization.

#### Scenario: Existing invocation still works
- **WHEN** the user invokes the CLI through the current module or installed script entry point
- **THEN** the CLI SHALL remain callable without requiring users to switch to a new command path
