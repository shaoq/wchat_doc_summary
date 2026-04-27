## ADDED Requirements

### Requirement: Market summary shall include structured outlook and strategy sections
The system SHALL generate market summaries with stable sections for next-session observation and follow-up strategy guidance, instead of leaving strategy commentary optional or floating across sections.

#### Scenario: Stable strategy sections in normal runs
- **WHEN** the system generates a market summary with sufficient market and news inputs
- **THEN** the summary SHALL include a dedicated `明日观察` section
- **AND** the summary SHALL include a dedicated `后续策略建议与风险提示` section

#### Scenario: Strategy guidance stays separate from stock highlights
- **WHEN** the system generates the summary body
- **THEN** strategy guidance SHALL NOT be merged into the `个股亮点` or equivalent stock-highlights section

### Requirement: Market summary shall downgrade to observation mode when evidence is insufficient
The system SHALL reduce directional strategy output when key market evidence is incomplete or unreliable.

#### Scenario: Missing market breadth or theme evidence
- **WHEN** key evidence such as成交概况、板块强弱、涨停链条或核心新闻催化 is missing or clearly incomplete
- **THEN** the summary SHALL explicitly mention the evidence gap
- **AND** the summary SHALL prioritize observation items and risk reminders over directional strategy conclusions

#### Scenario: Data-sparse summary avoids strong positioning language
- **WHEN** the summary is generated under insufficient evidence conditions
- **THEN** the summary SHALL avoid presenting the market as having a confirmed主线 or clear positioning recommendation

