## ADDED Requirements

### Requirement: Theme registry SHALL feed automatic evidence preparation
The system SHALL use built-in themes, user theme configuration, accepted learned terms, active group metadata, and ignored/noise terms as inputs to automatic sector evidence preparation.

#### Scenario: Accepted theme terms help prepare a new sector
- **WHEN** a user initializes a sector whose name or evidence matches an accepted learned theme term
- **THEN** evidence preparation SHALL use that accepted term as a high-confidence theme signal where applicable
- **AND** it SHALL record the theme source in preparation diagnostics

#### Scenario: Built-in theme members can create proxy candidates
- **WHEN** a tracked sector belongs to a built-in theme with related market-sector members
- **THEN** evidence preparation MAY create proxy market candidates from those related members
- **AND** it SHALL classify them as proxy evidence rather than exact aliases

#### Scenario: Noise terms are excluded from preparation
- **WHEN** a term is configured as ignored or noise
- **THEN** automatic evidence preparation SHALL NOT use that term to create aliases, theme links, or market proxy candidates

### Requirement: Automatic preparation SHALL not bypass theme review semantics
The system SHALL use accepted theme knowledge automatically but SHALL NOT silently accept pending theme suggestions or create formal memberships from unreviewed theme output.

#### Scenario: Pending theme suggestion remains pending
- **WHEN** a term has a pending theme-learning suggestion
- **THEN** automatic evidence preparation MAY use it only as low or medium confidence diagnostic evidence
- **AND** it SHALL NOT treat it as an accepted high-confidence theme term

#### Scenario: Preparation can emit reviewable suggestions
- **WHEN** automatic evidence preparation repeatedly finds a medium-confidence theme relationship
- **THEN** the system MAY create or refresh a pending theme-term suggestion for user review
- **AND** it SHALL NOT apply that relationship as an accepted term until the user accepts it

### Requirement: Theme diagnostics SHALL explain preparation inputs
The system SHALL expose which theme sources influenced automatic evidence preparation so users can audit automatic matches.

#### Scenario: Theme source appears in diagnostics
- **WHEN** automatic evidence preparation uses a built-in, user-configured, accepted learned, or active-group theme source
- **THEN** diagnostics SHALL identify the source layer and matched terms where available

#### Scenario: Disabled or conflicting terms appear as skipped
- **WHEN** a potential preparation match is skipped because of disabled, ignored, noise, or conflict settings
- **THEN** diagnostics SHALL record the skip reason where available
