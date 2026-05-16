## Requirements

### Requirement: System SHALL load sector group themes from multiple sources
The system SHALL build a runtime sector group theme registry from built-in defaults, user configuration, accepted learned terms, active group metadata, and ignored/noise term settings.

#### Scenario: Built-in themes are available without config
- **WHEN** no user theme configuration exists
- **THEN** the system SHALL load built-in sector group themes
- **AND** existing group suggestion behavior SHALL remain available

#### Scenario: User config overrides built-in themes
- **WHEN** a user theme configuration defines members or disabled terms for a built-in theme
- **THEN** the system SHALL apply the user configuration with higher priority than the built-in default

#### Scenario: Noise terms override theme membership
- **WHEN** a term is listed as an ignored or noise term
- **THEN** the system SHALL NOT use that term as a theme member during group suggestion matching
- **AND** it SHALL NOT generate theme-learning suggestions for that unchanged term

### Requirement: System SHALL expose theme dictionary management commands
The system SHALL provide CLI commands for users to inspect, validate, add, remove, disable, and ignore sector group theme terms.

#### Scenario: List configured themes
- **WHEN** a user runs `wchat ai sector-trends groups themes`
- **THEN** the system SHALL list known themes with source, member count, and disabled/noise indicators when available

#### Scenario: Show a theme
- **WHEN** a user runs `wchat ai sector-trends groups themes show --theme 人形机器人链`
- **THEN** the system SHALL show theme members, aliases, source layers, disabled members, and learned terms when available

#### Scenario: Add a theme member manually
- **WHEN** a user runs `wchat ai sector-trends groups themes add --theme 人形机器人链 --member 智能机器`
- **THEN** the system SHALL persist the member in the user-maintained theme dictionary
- **AND** subsequent group suggestions SHALL be able to match `智能机器` to `人形机器人链`

#### Scenario: Validate theme conflicts
- **WHEN** a user runs `wchat ai sector-trends groups themes validate`
- **THEN** the system SHALL report duplicate terms, cross-theme conflicts, disabled-term conflicts, and noise-term conflicts
- **AND** validation SHALL NOT modify the dictionary

### Requirement: System SHALL discover theme term suggestions from market evidence
The system SHALL discover candidate theme terms from structured market data, CLS watch data, market summaries, accepted group suggestions, and active group metadata.

#### Scenario: Market summary creates a candidate term
- **WHEN** a market summary identifies `机器人与智能机器主线`
- **AND** `智能机器` is not already mapped to an active theme
- **THEN** the system SHALL consider `智能机器` as a theme-term candidate with market-summary evidence

#### Scenario: CLS watch titles create a candidate term
- **WHEN** CLS watch titles repeatedly mention a sector or theme term within the lookback window
- **THEN** the system SHALL consider that term as a theme-term candidate
- **AND** it SHALL retain title references in suggestion evidence when available

#### Scenario: Low-evidence candidates are not shown
- **WHEN** a candidate term does not meet the configured or default evidence threshold
- **THEN** the system SHALL NOT create a pending theme-term suggestion for that term

### Requirement: System SHALL use AI to classify theme term candidates
The system SHALL use AI classification after rule-based scoring to recommend whether a candidate term belongs to an existing theme, should create a new theme, should be marked as noise, or should be ignored.

#### Scenario: AI maps candidate to existing theme
- **WHEN** a candidate term such as `智能机器` has evidence related to `人形机器人链`
- **AND** AI returns a valid high-confidence classification for the existing theme
- **THEN** the system SHALL create a pending `add_to_existing_theme` suggestion
- **AND** the suggestion SHALL include the target theme, term, confidence, reason, and evidence references

#### Scenario: AI proposes a new theme
- **WHEN** a candidate cluster has coherent evidence but does not fit any existing theme
- **AND** AI returns a valid high-confidence new-theme classification
- **THEN** the system SHALL create a pending `create_theme` suggestion with a suggested theme name and initial members

#### Scenario: AI marks noisy term
- **WHEN** a candidate term is a trading attribute or non-industry concept such as `本月解禁`
- **AND** AI classifies it as noise with sufficient confidence
- **THEN** the system SHALL create a pending `mark_noise` suggestion rather than adding it to an industry-chain theme

#### Scenario: Invalid AI output is discarded
- **WHEN** AI returns invalid JSON, adds unsupported actions, or provides confidence below threshold
- **THEN** the system SHALL NOT create a theme-term suggestion from that AI result

### Requirement: System SHALL require review before learning theme terms
The system SHALL persist discovered theme-term suggestions as pending records and only update the effective theme dictionary after explicit user acceptance.

#### Scenario: Review pending theme suggestions
- **WHEN** a user runs `wchat ai sector-trends groups themes suggestions`
- **THEN** the system SHALL list pending theme-term suggestions with action, term, target theme, confidence, source evidence, and reason

#### Scenario: Accept add-to-existing-theme suggestion
- **WHEN** a user accepts a pending `add_to_existing_theme` suggestion
- **THEN** the system SHALL add the term to the effective theme dictionary
- **AND** it SHALL mark the suggestion as accepted

#### Scenario: Accept create-theme suggestion
- **WHEN** a user accepts a pending `create_theme` suggestion
- **THEN** the system SHALL create the theme dictionary entry with the suggested initial members
- **AND** it SHALL mark the suggestion as accepted

#### Scenario: Ignore unchanged theme suggestion
- **WHEN** a user ignores a pending theme-term suggestion
- **THEN** the system SHALL mark it ignored
- **AND** future theme-term discovery SHALL NOT show the same unchanged suggestion again

### Requirement: System SHALL feed accepted learning back into group suggestions
The system SHALL use accepted theme dictionary changes in subsequent sector group suggestion generation without automatically changing formal sector groups.

#### Scenario: Accepted term affects future group suggestions
- **WHEN** a user accepts `智能机器` into `人形机器人链`
- **AND** the user later runs `wchat ai sector-trends groups suggest`
- **THEN** the system SHALL treat `智能机器` as a member of `人形机器人链` during theme matching

#### Scenario: Learning does not create formal membership
- **WHEN** a theme-term suggestion is accepted
- **THEN** the system SHALL NOT create a `SectorGroupMember`
- **AND** it SHALL NOT promote any `TrackedSector` status

#### Scenario: Accepted group suggestion can produce learning suggestion
- **WHEN** a user accepts a sector group suggestion containing cleaned members not yet in the theme dictionary
- **THEN** the system MAY create pending theme-term suggestions for those members
- **AND** it SHALL NOT automatically add them to the dictionary without review
