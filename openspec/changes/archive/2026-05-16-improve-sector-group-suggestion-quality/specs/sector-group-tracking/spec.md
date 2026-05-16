## ADDED Requirements

### Requirement: System SHALL constrain group suggestions with semantic themes
The system SHALL apply semantic theme constraints when generating sector group suggestions so weak co-occurrence signals do not create cross-theme industry-chain suggestions.

#### Scenario: Market-cache co-occurrence is not enough for a new group
- **WHEN** candidate sectors only co-occur because they appear on the same `market_sectors` trade dates
- **AND** the candidates do not share a semantic theme or pass AI semantic cleaning
- **THEN** the system SHALL NOT create a pending `new_group` suggestion for those mixed candidates

#### Scenario: Same-theme market-cache candidates can produce a suggestion
- **WHEN** market-cache co-occurrence candidates match the same built-in semantic theme
- **AND** the candidates include at least two eligible non-ignored sectors
- **THEN** the system SHALL create or refresh a pending suggestion for that semantic theme
- **AND** the suggestion SHALL record that market-cache co-occurrence was a weak evidence source

#### Scenario: Cross-theme members are excluded
- **WHEN** a candidate cluster contains sectors from unrelated themes such as `猪肉` and `宽带提速`
- **THEN** the system SHALL exclude unrelated members from the final pending suggestion
- **AND** it SHALL record the exclusion reason in suggestion evidence when available

### Requirement: System SHALL use AI to semantically clean group suggestion candidates
The system SHALL use AI semantic cleaning after rule-based candidate generation to validate whether candidate members belong to the same theme or industry chain before persisting pending suggestions.

#### Scenario: AI accepts a coherent candidate cluster
- **WHEN** rule-based generation produces a candidate cluster such as `光伏`, `TOPCon`, `BC电池`, `HIT电池`, and `钙钛矿`
- **AND** AI semantic cleaning returns a valid structured result accepting the cluster
- **THEN** the system SHALL persist a pending suggestion with the AI-approved group name, members, relationship types, confidence, and reasons

#### Scenario: AI removes unrelated members
- **WHEN** rule-based generation produces a candidate cluster containing unrelated members
- **AND** AI semantic cleaning rejects one or more members as unrelated
- **THEN** the system SHALL omit rejected members from `SectorGroupSuggestionMember`
- **AND** it SHALL store rejected member names and rejection reasons in suggestion evidence when available

#### Scenario: AI cannot add unknown members
- **WHEN** AI semantic cleaning returns a member that was not present in the input candidate pool
- **THEN** the system SHALL ignore that AI-added member
- **AND** it SHALL NOT create or initialize a `TrackedSector` from AI output during suggestion generation

#### Scenario: AI failure falls back safely
- **WHEN** AI semantic cleaning fails, times out, returns invalid JSON, or returns a low-confidence result
- **THEN** the system SHALL fall back to deterministic rule validation
- **AND** it SHALL only persist suggestions that pass semantic theme constraints
- **AND** it SHALL NOT persist obvious cross-theme mixed suggestions

### Requirement: System SHALL explain group suggestion quality and evidence
The system SHALL preserve explainable evidence for each generated group suggestion so users can understand whether it came from strong semantic signals, weak market co-occurrence, AI cleaning, or a combination of sources.

#### Scenario: Suggestion records source and cleaning evidence
- **WHEN** the system creates or refreshes a pending group suggestion
- **THEN** it SHALL store evidence including source signals, theme matches, AI cleaning status, accepted members, rejected members, and confidence rationale when available

#### Scenario: Suggestion reason distinguishes weak co-occurrence
- **WHEN** a pending suggestion is generated primarily from `market_sectors` co-occurrence
- **THEN** the suggestion reason SHALL identify it as a market-cache co-occurrence clue rather than a confirmed industry-chain relationship

#### Scenario: Suggestion review shows cleaned members
- **WHEN** a user runs `wchat ai sector-trends groups suggestions`
- **THEN** the system SHALL show only members included in the final cleaned suggestion
- **AND** it SHALL keep enough evidence for rejected members to be inspected or tested from stored suggestion evidence
