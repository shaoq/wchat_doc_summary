## ADDED Requirements

### Requirement: AI content-safety retry SHALL be stage-aware

The AI processing layer SHALL identify the logical generation stage when handling provider content-safety failures so callers and logs can distinguish required generation from optional enrichment.

#### Scenario: Content-safety log identifies generation stage
- **WHEN** an AI call fails due to provider content safety review
- **THEN** the retry or failure log SHALL include enough stage context to identify the failed operation
- **AND** market-summary callers SHALL be able to distinguish initial summary generation from strategy enhancement

#### Scenario: Repeated safety rejection does not hide unchanged retry input
- **WHEN** a prompt has already been sanitized after a content-safety failure
- **AND** subsequent retries still fail due to content safety review
- **THEN** the system SHALL NOT imply that additional sanitization was applied
- **AND** the final error path SHALL preserve the original provider error for diagnostics

### Requirement: AI prompt sanitization SHALL preserve structured factual evidence

The AI processing layer SHALL remove or mask risky free-text content without distorting structured factual evidence used by downstream summaries.

#### Scenario: Sanitization preserves market-data facts
- **WHEN** sanitization is applied to a market-summary prompt containing numeric and structured market facts
- **THEN** the sanitized prompt SHALL preserve index values, turnover, breadth counts, sector names, stock names, and source availability statements unless the exact free-text item is removed as risky content

#### Scenario: Sanitization marks removed event evidence as unavailable
- **WHEN** sanitization removes or masks event-title evidence from an AI prompt
- **THEN** the remaining prompt SHALL retain enough context for the model to treat that event class as unavailable or insufficient
- **AND** the prompt SHALL NOT convert removed event evidence into a stronger market conclusion
