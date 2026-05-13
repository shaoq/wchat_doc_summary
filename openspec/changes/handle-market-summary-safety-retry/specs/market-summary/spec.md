## ADDED Requirements

### Requirement: Market-summary SHALL preserve first-pass summary when strategy enhancement is safety-blocked

The system SHALL treat strategy enhancement as optional enrichment after a successful first-pass market summary and SHALL preserve the first-pass summary when only the enhancement call is rejected by provider content safety review.

#### Scenario: Strategy enhancement content-safety failure degrades successfully
- **WHEN** `wchat ai market-summary` generates a first-pass market summary successfully
- **AND** the generated strategy section is considered weak enough to trigger strategy enhancement
- **AND** the strategy-enhancement LLM call fails due to provider content safety review after configured retry handling
- **THEN** the system SHALL return the first-pass market summary
- **AND** the command SHALL continue to the normal save path
- **AND** the system SHALL log that strategy enhancement was skipped because of content safety review

#### Scenario: Initial summary content-safety failure remains fatal
- **WHEN** `wchat ai market-summary` calls the LLM for the initial full market summary
- **AND** the initial summary call fails due to provider content safety review after configured retry handling
- **THEN** the command SHALL fail instead of fabricating a summary without a successful first-pass result

### Requirement: Market-summary strategy enhancement SHALL use reduced evidence-bound inputs

The system SHALL build strategy-enhancement prompts from structured strategy evidence and concise prior-context signals instead of requiring full generated summary prose or raw event-heavy titles.

#### Scenario: Strategy enhancement prompt preserves market facts
- **WHEN** the system builds the strategy-enhancement prompt
- **THEN** the prompt SHALL preserve structured market facts including index summary, turnover, breadth, sector candidates, stock samples, global-market context status, and data gaps
- **AND** the prompt SHALL be able to omit or mask risky free-text event titles without changing those structured facts

#### Scenario: Reduced event evidence forces conservative strategy wording
- **WHEN** strategy-enhancement input has removed, masked, or insufficient event evidence
- **THEN** the prompt SHALL instruct the model to use observation, waiting-for-confirmation, or no-judgment language for event-driven strategy
- **AND** it SHALL NOT ask the model to infer specific event catalysts from missing evidence
