## ADDED Requirements

### Requirement: Market-summary SHALL expose fallback-aware overseas market context status

The system SHALL provide enough normalized overseas market context metadata for `market-summary` CLI output and AI prompt generation to distinguish primary success, fallback success, and total upstream failure.

#### Scenario: CLI shows fallback success semantics
- **WHEN** stage 1 of `wchat ai market-summary` renders a partially degraded but usable overseas market context
- **THEN** the CLI SHALL be able to communicate that the primary provider failed
- **AND** it SHALL be able to communicate which fallback provider supplied the final usable context

#### Scenario: Prompt blocks inference on upstream authorization failure
- **WHEN** all overseas market context providers fail and the terminal failure type is `unauthorized`
- **THEN** the AI input contract SHALL preserve that failure type in structured form
- **AND** the prompt gap instructions SHALL tell the model not to infer overnight U.S. market behavior from missing signals
