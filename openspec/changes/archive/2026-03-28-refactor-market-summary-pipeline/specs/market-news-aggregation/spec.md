## ADDED Requirements

### Requirement: Market summary aggregates multiple market news sources
The system SHALL aggregate market news for summary generation from财联社重要电报、财联社看盘数据和本地市场相关文章.

#### Scenario: Aggregate all available sources
- **WHEN** market summary generation starts for a trade date
- **THEN** the system SHALL collect available CLS telegraphs, CLS watch items, and related articles for that trade date
- **AND** the aggregated result SHALL be passed to the summary generation flow as separate structured inputs

### Requirement: Missing single news sources do not block summary generation
The system SHALL tolerate partial source availability during market news aggregation.

#### Scenario: CLS watch data unavailable
- **WHEN** CLS watch data is unavailable but CLS telegraphs or related articles are available
- **THEN** the system SHALL continue summary generation with the remaining available sources
- **AND** the aggregated news payload SHALL preserve source-specific empty sections instead of failing the whole request

#### Scenario: CLS telegraphs unavailable
- **WHEN** CLS telegraphs are unavailable but CLS watch data or related articles are available
- **THEN** the system SHALL continue summary generation with the remaining available sources
- **AND** the aggregated news payload SHALL preserve source-specific empty sections instead of failing the whole request

### Requirement: Aggregated news is prompt-ready and source-aware
The system SHALL preserve source boundaries when formatting market news for AI summary generation.

#### Scenario: Prompt input keeps source separation
- **WHEN** the aggregated market news payload is prepared for the AI processor
- **THEN** CLS telegraphs, CLS watch items, and related articles SHALL remain distinguishable inputs
- **AND** the AI prompt template SHALL be able to reference each source without depending on raw fetch-layer response formats
