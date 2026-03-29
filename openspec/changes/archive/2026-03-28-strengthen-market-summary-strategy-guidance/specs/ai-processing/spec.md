## ADDED Requirements

### Requirement: AI market summary generation shall organize evidence before strategy synthesis
The system SHALL present market-summary inputs to the model as explicit evidence groups so that strategy guidance is derived from structured facts rather than loosely concatenated raw text.

#### Scenario: Prompt groups evidence by analysis role
- **WHEN** `AIProcessor.generate_market_summary()` prepares a market-summary prompt
- **THEN** the prompt SHALL separate market snapshot, sector signals, stock-leadership clues, telegraph catalysts, watch-item rotation clues, and article viewpoints into distinct analysis groups

#### Scenario: Prompt discloses missing evidence
- **WHEN** one or more key evidence groups are empty or unreliable
- **THEN** the prompt SHALL explicitly state those gaps to the model
- **AND** the model SHALL be instructed to downgrade strategy confidence accordingly

### Requirement: AI strategy guidance shall be evidence-bound
The system SHALL require market-summary strategy guidance to reference explicit supporting signals and corresponding risks.

#### Scenario: Strategy guidance includes supporting basis
- **WHEN** the model outputs follow-up strategy guidance
- **THEN** each guidance item SHALL be tied to at least one explicit market, news, sector, or stock signal from the input evidence

#### Scenario: Strategy guidance includes risk or invalidation cues
- **WHEN** the model outputs follow-up strategy guidance
- **THEN** the output SHALL include corresponding risk reminders, invalidation cues, or fallback observation points
