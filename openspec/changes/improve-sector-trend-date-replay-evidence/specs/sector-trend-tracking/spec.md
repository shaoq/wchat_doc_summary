## ADDED Requirements

### Requirement: Date-specific updates SHALL repair local CLS watch sector attribution before trend generation
The system SHALL repair structured CLS watch sector attribution for the requested evidence window before collecting sector evidence for a date-specific sector trend update, unless the user explicitly disables the repair step.

#### Scenario: Batch date update repairs the evidence window once
- **WHEN** a user runs `wchat ai sector-trends update --all --date 2026-05-06 --days 10`
- **THEN** the system SHALL determine the evidence window ending on `2026-05-06`
- **AND** it SHALL repair existing local CLS watch rows in that window before per-sector evidence collection
- **AND** it SHALL reuse that repaired window for all sectors in the batch

#### Scenario: Single-sector date update repairs before collecting evidence
- **WHEN** a user runs `wchat ai sector-trends update --sector 光伏 --date 2026-05-06 --days 10`
- **THEN** the system SHALL repair existing local CLS watch rows in the requested evidence window before collecting evidence for `光伏`

#### Scenario: User skips automatic watch repair
- **WHEN** a user runs a date-specific sector trend update with the explicit skip-repair option
- **THEN** the system SHALL NOT repair CLS watch sector attribution before evidence collection
- **AND** it SHALL collect sector evidence from the currently persisted structured watch data

### Requirement: CLS watch sector repair SHALL populate structured sectors from auditable local evidence
The system SHALL enrich CLS watch rows with empty or missing structured `sectors` by using local watch content and local sector/theme dictionaries while preserving attribution provenance.

#### Scenario: Existing structured sectors are preserved
- **WHEN** a CLS watch row already has non-empty structured `sectors`
- **THEN** the repair process SHALL preserve those sectors
- **AND** it SHALL NOT replace them with lower-confidence text matches

#### Scenario: Empty sectors are inferred from local evidence
- **WHEN** a CLS watch row has empty structured `sectors`
- **AND** its title, content, stocks, tracked-sector aliases, or theme dictionary terms match known sector evidence
- **THEN** the repair process SHALL populate structured sector names for accepted matches
- **AND** it SHALL retain attribution diagnostics including match source, confidence, and matched terms where supported

#### Scenario: Low-confidence matches remain distinguishable
- **WHEN** a CLS watch row only matches weak text evidence
- **THEN** the repair process SHALL mark the attribution as low confidence in diagnostics or provenance
- **AND** downstream evidence collection SHALL be able to distinguish low-confidence watch matches from original structured sector tags

#### Scenario: Repair does not fetch missing raw watch data
- **WHEN** the requested evidence window has no local CLS watch rows for a date
- **THEN** the repair process SHALL report the local data gap
- **AND** it SHALL NOT perform an implicit network fetch for missing watch data

### Requirement: Date-specific updates SHALL use previous summaries before the target report date
The system SHALL select previous-summary context for date-specific sector trend updates using only summaries whose `end_date` is earlier than the target report date.

#### Scenario: Historical replay ignores future reports
- **WHEN** a sector has summaries on `2026-05-06` and `2026-05-15`
- **AND** the user reruns `wchat ai sector-trends update --sector TOPCon --date 2026-05-06 --force`
- **THEN** the system SHALL NOT use the `2026-05-15` summary as previous context

#### Scenario: Historical replay uses the nearest earlier report
- **WHEN** a sector has summaries on `2026-05-06` and `2026-05-07`
- **AND** the user runs `wchat ai sector-trends update --sector TOPCon --date 2026-05-08 --force`
- **THEN** the system SHALL use the `2026-05-07` summary as previous context

#### Scenario: First historical report remains initial assessment
- **WHEN** no summary exists before the target report date for a sector
- **AND** the user runs a date-specific update for that sector
- **THEN** the generated report SHALL treat the update as an initial tracking assessment

### Requirement: Sector evidence diagnostics SHALL distinguish data gaps from no-trend judgement
The system SHALL expose diagnostics for sector evidence collection and repair so users can understand whether conservative trend labels are caused by sparse data, missing structured sources, low-confidence attribution, or lack of directional evidence.

#### Scenario: Update output includes evidence source counts
- **WHEN** a sector trend update completes
- **THEN** the result diagnostics SHALL include counts for market appearances, CLS watch mentions, CLS telegraph mentions, and total evidence

#### Scenario: Diagnostics include repair results
- **WHEN** automatic CLS watch repair runs before a sector trend update
- **THEN** the result diagnostics SHALL include repaired-row counts, inferred-sector counts, and skipped or low-confidence match counts where available

#### Scenario: No-trend from missing evidence remains visible
- **WHEN** a generated report has `trend_status` equal to `暂无趋势`
- **AND** evidence collection had missing market, CLS watch, or CLS telegraph sources
- **THEN** the persisted evidence diagnostics SHALL preserve those data gaps for later history, matrix, or debugging views

### Requirement: Standalone CLS watch sector repair SHALL be available without generating reports
The system SHALL provide a CLI path to repair structured CLS watch sector attribution for a date or evidence window without generating sector trend reports.

#### Scenario: Repair command processes a target window
- **WHEN** a user runs the standalone CLS watch sector repair command for `--date 2026-05-06 --days 10`
- **THEN** the system SHALL repair existing local CLS watch rows in the computed evidence window
- **AND** it SHALL report repaired rows, unchanged rows, unmatched rows, and low-confidence matches

#### Scenario: Repair command does not generate sector reports
- **WHEN** a user runs the standalone CLS watch sector repair command
- **THEN** the system SHALL NOT create or overwrite files under `output/sector_trends/`
- **AND** it SHALL NOT create new sector trend summary rows

### Requirement: Conservative trend-stage validation SHALL remain unchanged by evidence repair
The system SHALL continue to apply existing trend-stage taxonomy validation after evidence repair and SHALL NOT promote sector stages solely because a watch row was text-matched.

#### Scenario: Weak repaired evidence remains conservative
- **WHEN** a sector has only low-confidence repaired watch evidence and no confirming market evidence
- **THEN** the generated trend status SHALL remain constrained by the existing conservative validation rules

#### Scenario: Repaired multi-source evidence can support existing allowed stages
- **WHEN** repaired watch attribution combines with market or telegraph evidence to satisfy existing evidence requirements
- **THEN** the system MAY generate any trend stage already allowed by the current taxonomy
- **AND** it SHALL still pass the service-level stage validation step
