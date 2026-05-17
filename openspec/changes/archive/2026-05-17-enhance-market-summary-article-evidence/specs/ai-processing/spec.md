## ADDED Requirements

### Requirement: AI processing SHALL extract structured market article evidence
The AI processing layer SHALL support a reusable processing task that extracts structured market article evidence from公众号 articles.

#### Scenario: Extract market article evidence from article content
- **WHEN** the system requests market article evidence for an article with title and content or summary
- **THEN** the AI processing layer SHALL return normalized structured evidence
- **AND** the evidence SHALL include article type, market relevance, time role, mentioned sectors, mentioned stocks, mainline views, sentiment view, next-day watch items, risk points, and a concise usable summary

#### Scenario: Low relevance article is classified conservatively
- **WHEN** an article does not contain meaningful A-share market review, strategy, sector, sentiment, or risk signals
- **THEN** the AI processing layer SHALL mark the article as low relevance or unrelated
- **AND** downstream market-summary generation SHALL be able to skip or down-rank that evidence

#### Scenario: Insufficient article content degrades without fabrication
- **WHEN** an article has only a title and lacks usable content or summary
- **THEN** the AI processing layer SHALL either return a low-confidence title-derived evidence record or report that evidence is unavailable
- **AND** it SHALL NOT invent sectors, stocks, mainline views, watch items, or risks that are not present in the available article fields

### Requirement: AI processing SHALL cache market article evidence
The AI processing layer SHALL persist generated market article evidence so repeated market-summary runs can reuse it.

#### Scenario: Successful evidence extraction is persisted
- **WHEN** market article evidence extraction succeeds for an article
- **THEN** the system SHALL persist the normalized evidence using an article-processing task record
- **AND** future runs SHALL be able to retrieve that evidence by article ID and task type

#### Scenario: Cached evidence can be refreshed by force policy
- **WHEN** a caller requests evidence preparation with force refresh enabled
- **AND** cached market article evidence already exists for an article
- **THEN** the AI processing layer SHALL allow the cached evidence to be regenerated or replaced according to the caller's force policy
- **AND** the refresh behavior SHALL be observable through diagnostics

#### Scenario: Malformed cached evidence is not trusted silently
- **WHEN** cached market article evidence exists
- **AND** the cached JSON is malformed or missing required normalized fields
- **THEN** the AI processing layer SHALL treat the evidence as invalid
- **AND** it SHALL regenerate the evidence when allowed or report a degraded fallback when regeneration is not allowed

### Requirement: AI processing SHALL provide bounded batch evidence preparation
The AI processing layer SHALL support bounded batch preparation of market article evidence for selected article candidates.

#### Scenario: Batch preparation limits LLM calls
- **WHEN** market-summary selects article candidates for evidence preparation
- **THEN** the AI processing layer SHALL process only the bounded selected candidate set
- **AND** it SHALL avoid sending every article from the raw article window to the LLM

#### Scenario: Batch preparation returns per-article outcomes
- **WHEN** batch market article evidence preparation completes
- **THEN** the AI processing layer SHALL return per-article outcomes for prepared, reused, skipped, failed, invalid, and fallback evidence
- **AND** market-summary diagnostics SHALL be able to aggregate those outcomes

### Requirement: AI processing prompts SHALL preserve article evidence boundaries
The AI processing prompt for market article evidence SHALL extract claims from the article rather than convert them into confirmed market facts.

#### Scenario: Prompt distinguishes author viewpoint from market fact
- **WHEN** the article evidence extraction prompt asks the model to identify mainline, sentiment, watch, or risk claims
- **THEN** the prompt SHALL require the model to express those items as article viewpoints or author claims
- **AND** it SHALL NOT ask the model to validate those claims against market data inside the article extraction step

#### Scenario: Prompt returns strict normalized JSON
- **WHEN** the AI processing layer requests market article evidence
- **THEN** the prompt SHALL require strict normalized JSON output
- **AND** the implementation SHALL parse and normalize the result before persisting or passing it downstream
