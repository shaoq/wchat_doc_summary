## ADDED Requirements

### Requirement: Module entry point remains executable after CLI modularization

The system SHALL keep `python -m src.cli` executable after the CLI is reorganized into a package.

#### Scenario: Root help works through module execution
- **WHEN** the user runs `python -m src.cli --help`
- **THEN** the system displays the unified root CLI help output
- **AND** the command exits successfully

#### Scenario: AI help works through module execution
- **WHEN** the user runs `python -m src.cli ai --help`
- **THEN** the system displays the `ai` command group's help output
- **AND** the command exits successfully

### Requirement: Module and installed-script entry points share the same command surface

The system SHALL expose the same command tree through the installed script entry point and the module entry point.

#### Scenario: Top-level commands match
- **WHEN** the user inspects the CLI through the installed script entry point and through `python -m src.cli`
- **THEN** the same top-level commands SHALL be registered under both invocation methods

#### Scenario: AI subcommands match
- **WHEN** the user inspects `ai` subcommands through the installed script entry point and through `python -m src.cli ai --help`
- **THEN** the same `ai` subcommands SHALL be registered under both invocation methods
