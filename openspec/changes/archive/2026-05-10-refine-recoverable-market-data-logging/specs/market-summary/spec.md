## ADDED Requirements

### Requirement: Market-summary stage output reflects final market data status

The market-summary command SHALL present market data collection status based on final normalized outcomes, not intermediate recoverable source-attempt failures.

#### Scenario: recoverable market data attempts succeed through fallback
- **WHEN** `wchat ai market-summary` collects market data
- **AND** one or more upstream attempts fail but fallback or later hosts produce usable data
- **THEN** stage 1 SHALL display the final successful, near-complete, or fallback status
- **AND** stage 1 SHALL NOT present the recoverable attempt failure as the primary market data outcome

#### Scenario: market data source category is finally unavailable
- **WHEN** `wchat ai market-summary` collects market data
- **AND** all configured upstreams for a market data category fail
- **THEN** stage 1 SHALL display the normalized error or degraded status for that category
- **AND** the logs SHALL include a single final failure summary for that category rather than multiple recoverable attempt warnings
