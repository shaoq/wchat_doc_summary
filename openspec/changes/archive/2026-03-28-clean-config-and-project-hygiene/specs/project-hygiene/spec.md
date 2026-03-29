## ADDED Requirements

### Requirement: Project configuration avoids duplicate field definitions
The system SHALL avoid duplicate configuration field definitions within the primary settings module.

#### Scenario: Single source of truth for config field
- **WHEN** a configuration field is defined in the settings module
- **THEN** that field SHALL have a single authoritative definition in the module

### Requirement: Project documentation reflects current CLI capabilities
The system SHALL keep the primary README aligned with the current stable CLI surface.

#### Scenario: README lists current user-facing capabilities
- **WHEN** a maintainer reads the primary README
- **THEN** the documented quick-start commands and feature summary SHALL reflect the current stable CLI capabilities

### Requirement: Derived cache artifacts are not treated as maintained source files
The system SHALL avoid keeping generated cache artifacts as maintained project files.

#### Scenario: Python cache artifacts
- **WHEN** Python cache artifacts such as `__pycache__` outputs are generated locally
- **THEN** they SHALL NOT be treated as long-term maintained project artifacts

#### Scenario: Temporary backup file
- **WHEN** a temporary source backup file is no longer part of an active migration plan
- **THEN** it SHALL NOT remain as a maintained project artifact
