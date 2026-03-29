## ADDED Requirements

### Requirement: Historical market summaries can be listed without LLM configuration

The system SHALL allow users to list saved historical market summaries without requiring LLM API configuration, because listing is a local read-only operation.

#### Scenario: List summaries without LLM API Key
- **WHEN** the user executes `wchat ai market-summary --list`
- **AND** no LLM API Key is configured
- **THEN** the system displays the saved summary list successfully
- **AND** the command SHALL NOT fail due to AI processor initialization
