## ADDED Requirements

### Requirement: Market summary CLI shall close data-collection stages before AI generation

The system SHALL enter the AI summary-generation stage only after market-data collection and news-data collection have both completed and their final normalized input states are available for inspection.

#### Scenario: Start AI only after all collection attempts settle
- **WHEN** user executes `wchat ai market-summary`
- **THEN** the CLI SHALL complete stage 1 and stage 2 collection work, including any fallback or degraded data-source attempts, before invoking AI summary generation
- **AND** the pre-generation input manifest SHALL reflect the final `ok / partial / empty / error` state that the AI stage will actually consume

#### Scenario: Keep stage output free from raw third-party progress bars
- **WHEN** a `market-summary` data source internally performs paginated fallback work during stage 1
- **THEN** the CLI SHALL NOT emit the source library's raw progress-bar lines or terminal control characters to the user
- **AND** the visible output between stage boundaries SHALL remain limited to the command's managed stage headers, status lines, and summaries
