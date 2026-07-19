## ADDED Requirements

### Requirement: Theme definitions SHALL align to Shenwan industry naming

The `THEME_DEFINITIONS` member terms SHALL be rewritten to Shenwan level-1 (SW1) industry naming conventions so that theme grouping works after the taxonomy cold start.

#### Scenario: Theme members matched under SW1

- **WHEN** a theme group is resolved after cold start
- **THEN** its member terms SHALL match SW1 industry names from the active sectors source
- **AND** unmatched legacy east-money concept terms SHALL be flagged for review and replacement
