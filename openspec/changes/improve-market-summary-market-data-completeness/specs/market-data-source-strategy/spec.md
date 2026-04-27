## MODIFIED Requirements

### Requirement: Rise-fall statistics use a pytdx A-share quote strategy

The system SHALL compute rise-fall statistics from `pytdx` quotes over an explicitly filtered A-share universe, and SHALL attempt bounded targeted recovery for missing quote items before finalizing the quality status.

#### Scenario: pytdx quote aggregation succeeds completely
- **WHEN** the system can fetch `pytdx` quotes for the maintained A-share universe
- **THEN** it SHALL compute `up_count`, `down_count`, and `flat_count` from `price` and `last_close`
- **AND** the universe SHALL only include supported A-share prefixes
- **AND** the final quality status SHALL be `ok`

#### Scenario: pytdx quote aggregation is near complete after recovery
- **WHEN** the initial `pytdx` quote aggregation misses a small number of securities
- **AND** the system performs the declared targeted recovery for the missing securities
- **AND** the remaining gap stays within the declared near-complete threshold
- **THEN** the system SHALL return the computed statistics instead of zero values
- **AND** the final quality status SHALL be `near-complete`
- **AND** the quality metadata SHALL include both actual and expected sample counts

#### Scenario: pytdx quote aggregation remains meaningfully incomplete
- **WHEN** the `pytdx` quote strategy still has a remaining gap larger than the declared near-complete threshold after targeted recovery
- **THEN** the system SHALL return the computed partial statistics instead of zero values
- **AND** the final quality status SHALL be `partial`
- **AND** the quality metadata SHALL include both actual and expected sample counts

#### Scenario: pytdx quote aggregation fails entirely
- **WHEN** the `pytdx` quote strategy is unavailable or produces no usable quote samples
- **THEN** the system SHALL return the normalized zero-value statistics contract
- **AND** the final quality status SHALL be `error`

## ADDED Requirements

### Requirement: Limit-up stocks preserve the fullest available source result

The system SHALL preserve the fullest available limit-up stock set from the selected source strategy, and SHALL NOT truncate the normalized data-layer result to a fixed top-N size.

#### Scenario: Dedicated limit-up pool returns a full result set
- **WHEN** the dedicated limit-up pool source succeeds for a trade date
- **THEN** the system SHALL normalize and preserve the full result set returned by that source
- **AND** it SHALL NOT truncate the data-layer result to 20 items merely for summary display

#### Scenario: Snapshot fallback returns approximate candidates
- **WHEN** the dedicated limit-up pool source is unavailable
- **AND** the system falls back to a snapshot-based or broad-market fallback strategy
- **THEN** the system SHALL preserve the fallback candidate set instead of truncating it to a fixed top-N size
- **AND** the returned metadata SHALL make clear that the result is an approximate candidate set rather than the dedicated limit-up pool

### Requirement: Sector summary input expands to top ten and bottom ten

The system SHALL provide twenty sector items for market-summary sector context, consisting of the top ten advancing sectors and bottom ten declining sectors from the selected sector source.

#### Scenario: Sector source returns enough rows
- **WHEN** a selected sector source returns at least twenty normalized sector rows
- **THEN** the system SHALL return `top_sectors` with 10 items
- **AND** it SHALL return `bottom_sectors` with 10 items

#### Scenario: Sector source returns fewer than twenty rows
- **WHEN** a selected sector source returns fewer than twenty normalized sector rows
- **THEN** the system SHALL preserve the available ordering semantics
- **AND** it SHALL return as many top and bottom sector rows as are actually available without fabricating data
