## ADDED Requirements

### Requirement: Market-summary SHALL prepare structured公众号 article evidence automatically
The system SHALL prepare structured market article evidence for locally available公众号 articles in the market-summary article window before generating the market summary.

#### Scenario: Online summary prepares missing article evidence
- **WHEN** `wchat ai market-summary` runs in online mode for a target trade date
- **AND** local articles exist in the article window for that target trade date
- **AND** one or more selected article candidates do not have cached market article evidence
- **THEN** the system SHALL automatically generate structured market article evidence for those selected candidates
- **AND** the generated evidence SHALL be included in the news payload used for summary generation

#### Scenario: Cached article evidence is reused
- **WHEN** `wchat ai market-summary` runs for a target trade date
- **AND** selected article candidates already have valid cached market article evidence
- **THEN** the system SHALL reuse the cached evidence without requiring users to run article summarization commands manually
- **AND** the final summary generation SHALL receive the cached structured evidence

#### Scenario: Article evidence preparation failure degrades summary generation
- **WHEN** selected local articles exist for the target article window
- **AND** structured evidence generation fails for one or more articles
- **THEN** the system SHALL continue market-summary generation with available article evidence and fallback article title or summary signals
- **AND** the article source diagnostics SHALL report the preparation failure without marking all news collection as failed when other news sources remain usable

### Requirement: Market-summary SHALL select articles by market relevance before prompt injection
The system SHALL rank and select article candidates using market relevance signals before injecting article evidence into market-summary prompts.

#### Scenario: Relevant review articles outrank raw recency
- **WHEN** the article window contains more articles than the prompt can consume
- **AND** some articles contain review, strategy, mainline, sector, sentiment, limit-up, watchlist, or risk signals
- **THEN** the system SHALL prefer those market-relevant articles over less relevant articles that are merely newer
- **AND** the selected article evidence SHALL remain bounded to a configured maximum candidate count

#### Scenario: Feed metadata participates in article selection
- **WHEN** selected article candidates can be joined to feed metadata
- **THEN** the system SHALL make feed name and feed weight available to article selection and diagnostics
- **AND** missing feed metadata SHALL NOT prevent article selection or summary generation

### Requirement: Market-summary SHALL treat公众号 articles as secondary viewpoint evidence
The system SHALL treat structured公众号 article evidence as viewpoint evidence that supplements market facts and SHALL NOT use it to override contradictory or missing primary market evidence.

#### Scenario: Article-only mainline remains a viewpoint
- **WHEN** structured article evidence claims a sector or theme is the mainline
- **AND** market data, CLS watch data, CLS telegraphs, sector performance, and limit-up evidence do not support that claim
- **THEN** the generated market summary SHALL describe the article signal as a viewpoint, watch item, or hypothesis
- **AND** it SHALL NOT state that the sector or theme is a confirmed market mainline solely because of the article evidence

#### Scenario: Article evidence can reinforce supported market facts
- **WHEN** structured article evidence aligns with market data, CLS watch data, CLS telegraphs, sector performance, or limit-up evidence
- **THEN** the generated market summary MAY use the article evidence as reinforcement for mainline, rotation, sentiment, next-day watch, or risk analysis
- **AND** the summary SHALL still cite or reflect the supporting primary market evidence where available

### Requirement: Historical forced market-summary runs SHALL backfill local article evidence
The system SHALL allow historical forced market-summary generation to automatically backfill missing structured article evidence from local historical articles for the requested target date.

#### Scenario: Historical force run backfills from local articles
- **WHEN** the user runs `wchat ai market-summary --date <date> --force`
- **AND** local articles exist in the computed article window for `<date>`
- **AND** selected articles are missing structured market article evidence
- **THEN** the system SHALL generate or refresh the missing local article evidence according to the force policy
- **AND** the regenerated market summary SHALL consume the prepared structured article evidence

#### Scenario: Historical force run cannot fabricate missing articles
- **WHEN** the user runs `wchat ai market-summary --date <date> --force`
- **AND** no local articles exist in the computed article window for `<date>`
- **THEN** the system SHALL report article evidence as unavailable or empty
- **AND** it SHALL NOT fabricate article viewpoints or imply that article evidence was prepared

#### Scenario: Existing summary without force still skips regeneration
- **WHEN** the user runs `wchat ai market-summary --date <date>` without `--force`
- **AND** a market summary already exists for `<date>`
- **THEN** the command SHALL preserve the existing skip behavior
- **AND** it SHALL NOT perform article evidence backfill for that date

### Requirement: Offline market-summary SHALL only use local cached article evidence
The system SHALL preserve offline mode as a local replay path for article evidence.

#### Scenario: Offline run reuses cached evidence
- **WHEN** the user runs `wchat ai market-summary --offline`
- **AND** selected local articles have valid cached market article evidence
- **THEN** the system SHALL reuse the cached evidence in summary generation
- **AND** it SHALL NOT fetch new articles

#### Scenario: Offline run does not generate missing article evidence by default
- **WHEN** the user runs `wchat ai market-summary --offline`
- **AND** selected local articles are missing structured market article evidence
- **THEN** the system SHALL NOT call the LLM to generate missing article evidence by default
- **AND** it SHALL degrade to existing local title, summary, or content-derived fallback signals

### Requirement: Market-summary SHALL expose article evidence diagnostics
The system SHALL expose normalized diagnostics describing article discovery, evidence preparation, selection, and degradation outcomes.

#### Scenario: CLI can report article evidence preparation outcome
- **WHEN** stage 2 of `wchat ai market-summary` finishes collecting news data
- **THEN** the CLI SHALL be able to report how many local articles were found, selected, prepared, reused, skipped, failed, or degraded for article evidence
- **AND** it SHALL preserve the existing normalized final source status semantics of `ok`, `empty`, or `error`

#### Scenario: Saved summary sources include article evidence provenance
- **WHEN** a market summary is saved after structured article evidence was used or attempted
- **THEN** the persisted summary source metadata SHALL include article evidence diagnostics or a compact provenance summary
- **AND** the metadata SHALL be sufficient to audit whether article evidence came from cached extraction, newly generated extraction, or fallback title/summary signals

### Requirement: Market-summary prompts SHALL consume structured article viewpoints
The system SHALL inject structured article viewpoints into the initial market-summary prompt and strategy-enhancement prompt instead of relying only on article titles.

#### Scenario: Initial prompt receives structured article evidence
- **WHEN** `AIProcessor.generate_market_summary()` builds the initial market-summary prompt
- **AND** structured article evidence is available
- **THEN** the prompt SHALL include article type, relevance, feed/source label when available, mentioned sectors or stocks, mainline viewpoints, sentiment views, next-day watch items, risk points, and usable summary fields
- **AND** it SHALL instruct the model to treat those fields as viewpoint evidence

#### Scenario: Strategy enhancement receives article watch and risk signals
- **WHEN** strategy enhancement is triggered
- **AND** structured article evidence is available
- **THEN** the strategy-enhancement prompt SHALL include compact article watch items and risk points
- **AND** it SHALL NOT rely only on raw article titles for the key-message strategy section
