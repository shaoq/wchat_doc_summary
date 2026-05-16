## ADDED Requirements

### Requirement: System SHALL manage sector groups above tracked sectors
The system SHALL provide a sector group layer that maps one theme or industry-chain group to one or more existing tracked sector records without merging or replacing the underlying sector records.

#### Scenario: Create sector group
- **WHEN** a user creates a sector group named `人形机器人`
- **THEN** the system SHALL persist a group identity for `人形机器人`
- **AND** it SHALL NOT create, rename, merge, or delete any existing `TrackedSector` record

#### Scenario: One sector belongs to multiple groups
- **WHEN** a sector such as `AI芯片` is added to multiple groups
- **THEN** the system SHALL allow multiple group memberships for the same sector
- **AND** each membership SHALL remain independently visible in group details

### Requirement: System SHALL manage group members with relationship metadata
The system SHALL store each group membership with structured relationship metadata so group-level analysis can distinguish core directions, upstream links, downstream links, materials, equipment, catalysts, and related members.

#### Scenario: Add member with relation type
- **WHEN** a user adds `减速器` to group `人形机器人` with relation type `upstream`
- **THEN** the system SHALL create a membership from the group to the sector
- **AND** the membership SHALL store the relation type `upstream`

#### Scenario: Prevent duplicate group membership
- **WHEN** the same sector is added to the same group more than once
- **THEN** the system SHALL keep only one formal membership for that group-sector pair
- **AND** it SHALL update metadata rather than creating a duplicate membership

### Requirement: System SHALL expose sector group CLI commands
The system SHALL expose group management under the existing `wchat ai sector-trends` command group.

#### Scenario: List sector groups
- **WHEN** a user runs `wchat ai sector-trends groups ls`
- **THEN** the system SHALL list known sector groups with status, member count, latest update date, and pending suggestion count when available

#### Scenario: Show sector group details
- **WHEN** a user runs `wchat ai sector-trends groups show --group 人形机器人`
- **THEN** the system SHALL show the group metadata and confirmed members
- **AND** each member row SHALL include sector status, relation type, latest seen date, latest sector update date, and latest group-relevant freshness metadata when available

#### Scenario: Add sector to group manually
- **WHEN** a user runs `wchat ai sector-trends groups add --group 人形机器人 --sector 减速器 --type upstream`
- **THEN** the system SHALL create or update the confirmed membership for `减速器`
- **AND** it SHALL NOT run AI trend generation as part of the membership edit

### Requirement: System SHALL generate sector group suggestions
The system SHALL generate pending suggestions for sector grouping from existing sectors and recent evidence instead of requiring all group mappings to be manually created.

#### Scenario: Suggest new sector group
- **WHEN** recent candidate or tracked sectors indicate a coherent theme that does not match an existing group
- **THEN** the system SHALL create a pending `new_group` suggestion
- **AND** the suggestion SHALL include a proposed group name, suggested members, confidence, reasons, and evidence

#### Scenario: Suggest adding members to existing group
- **WHEN** recent candidate or tracked sectors appear related to an existing group and are not already members
- **THEN** the system SHALL create a pending `add_members` suggestion for the existing group
- **AND** it SHALL prefer this suggestion type over creating a duplicate new group

#### Scenario: Suggest updating existing membership metadata
- **WHEN** a sector is already a group member but recent evidence indicates a different relationship type or materially different weight
- **THEN** the system SHALL create a pending `update_members` suggestion
- **AND** it SHALL include the current metadata and suggested replacement metadata

### Requirement: System SHALL deduplicate pending group suggestions
The system SHALL avoid repeatedly creating equivalent pending suggestions for the same target group and sector membership.

#### Scenario: Existing pending add-member suggestion is refreshed
- **WHEN** the system generates a suggestion for a group-sector pair that already has a pending add-member suggestion
- **THEN** it SHALL update the existing suggestion evidence, confidence, and timestamps
- **AND** it SHALL NOT create another pending suggestion for the same group-sector pair

#### Scenario: Confirmed membership suppresses add-member suggestion
- **WHEN** a sector is already a confirmed member of a group
- **THEN** the system SHALL NOT generate an `add_members` suggestion for that same group-sector pair

### Requirement: System SHALL respect sector status during group suggestion and acceptance
The system SHALL use sector status to control suggestion eligibility and acceptance behavior.

#### Scenario: Candidate sector appears in group suggestion
- **WHEN** a sector has status `candidate` and recent evidence links it to a sector group
- **THEN** the system MAY include it in a pending group suggestion
- **AND** it SHALL display the sector's current status in the suggestion details

#### Scenario: Ignored sector is excluded from suggestions
- **WHEN** a sector has status `ignored`
- **THEN** the system SHALL exclude it from group suggestions by default

#### Scenario: Accepting candidate member promotes by default
- **WHEN** a user accepts a suggestion that includes a sector with status `candidate`
- **THEN** the system SHALL promote that sector to `tracked` by default
- **AND** it SHALL display the status transition before or after acceptance

#### Scenario: Accepting candidate member can keep status
- **WHEN** a user accepts a suggestion with a keep-status option
- **THEN** the system SHALL add the sector to the group
- **AND** it SHALL preserve the sector's existing status

### Requirement: System SHALL support accepting and ignoring group suggestions
The system SHALL let users review pending suggestions and decide whether to accept, partially accept, or ignore them.

#### Scenario: Accept full suggestion
- **WHEN** a user accepts a pending group suggestion
- **THEN** the system SHALL create or update the relevant group and memberships
- **AND** it SHALL mark the suggestion as accepted

#### Scenario: Accept partial suggestion
- **WHEN** a user accepts only selected members from a pending suggestion
- **THEN** the system SHALL apply only the selected member changes
- **AND** it SHALL preserve an auditable outcome for omitted members

#### Scenario: Ignore suggestion
- **WHEN** a user ignores a pending group suggestion
- **THEN** the system SHALL mark the suggestion as ignored
- **AND** future suggestion generation SHALL NOT repeatedly show the same ignored relationship unless new evidence materially changes

### Requirement: System SHALL update sector group trends independently from sector trends
The system SHALL generate group-level trend reports that analyze confirmed group members together while preserving each member sector's independent trend history.

#### Scenario: Group update reads member summaries
- **WHEN** a user updates group `人形机器人`
- **THEN** the system SHALL read confirmed group members
- **AND** it SHALL collect each member's target-date or latest sector trend summary when available
- **AND** it SHALL collect recent group-relevant evidence for those members

#### Scenario: Group update creates group report
- **WHEN** group-level evidence is collected
- **THEN** the system SHALL generate a group trend report focused on cross-member structure
- **AND** the report SHALL analyze resonance, diffusion, rotation, core members, catch-up members, and retreat risk where evidence is available

#### Scenario: Group report does not replace sector reports
- **WHEN** a group trend report is saved
- **THEN** the system SHALL NOT overwrite any member sector trend report
- **AND** each member sector SHALL retain its own trend history

### Requirement: System SHALL refresh tracked members during group updates by default
The system SHALL refresh missing target-date sector reports for confirmed tracked members before generating a group trend report unless the user explicitly disables member refresh.

#### Scenario: Default group update refreshes missing tracked members
- **WHEN** a user runs a group update without member-refresh disabling options
- **THEN** the system SHALL run single-sector updates for confirmed tracked members that do not have a report for the target date before generating the group report
- **AND** it SHALL skip confirmed tracked members that already have a report for the target date unless force is requested
- **AND** it SHALL include member refresh and freshness information in the group report or update result

#### Scenario: Disable member refresh
- **WHEN** a user runs a group update with a no-refresh-members option
- **THEN** the system SHALL NOT run single-sector AI updates for group members
- **AND** it SHALL generate the group report from existing member summaries and recent raw evidence
- **AND** it SHALL mark stale or missing member summaries in the group report or update result

#### Scenario: Force refresh all members
- **WHEN** a user runs a group update with force refresh options
- **THEN** the system SHALL run single-sector updates for all eligible tracked members before generating the group report

#### Scenario: Candidate members are not refreshed by default
- **WHEN** a group contains a member sector that is still `candidate`
- **THEN** default member refresh SHALL NOT run AI analysis for that sector
- **AND** the group report SHALL mark that member as not formally tracked unless the user promotes it or explicitly includes candidates

### Requirement: System SHALL persist and view sector group trend history
The system SHALL store group-level trend reports separately from single-sector trend reports and allow users to view the latest report and history for a group.

#### Scenario: Show latest group report
- **WHEN** a user runs `wchat ai sector-trends groups show --group 人形机器人 --latest`
- **THEN** the system SHALL display the latest group trend report or its summary metadata
- **AND** it SHALL include the output path when available

#### Scenario: List group history
- **WHEN** a user runs `wchat ai sector-trends groups history --group 人形机器人`
- **THEN** the system SHALL list group trend reports in reverse chronological order
- **AND** each row SHALL include date, trend status or equivalent group label, member freshness summary, and report path when available

### Requirement: System SHALL provide stage-based CLI feedback for trend generation
The system SHALL provide stage-based terminal feedback for sector and group trend generation commands so users can understand progress, refresh behavior, failures, key labels, and generated file paths without reading the full report body in the terminal.

#### Scenario: Single sector update shows stages and output path
- **WHEN** a user runs `wchat ai sector-trends update --sector 减速器`
- **THEN** the system SHALL display stage headers for setup, evidence collection, AI generation, and result persistence
- **AND** it SHALL display concise stage conclusions, key trend labels, elapsed generation time when available, and the generated report path
- **AND** it SHALL NOT print the full report content by default

#### Scenario: Single group update shows member refresh plan and output path
- **WHEN** a user runs `wchat ai sector-trends groups update --group 人形机器人`
- **THEN** the system SHALL display the target group, target date, execution mode, member count, and member refresh strategy
- **AND** it SHALL display stages for member status checks, member refresh, group evidence collection, AI generation, and result persistence
- **AND** it SHALL display refreshed, skipped, failed, candidate, or stale member statuses where applicable
- **AND** it SHALL display the generated group report path
- **AND** it SHALL NOT print the full group report content by default

#### Scenario: Batch sector update shows summary rows
- **WHEN** a user runs `wchat ai sector-trends update --all`
- **THEN** the system SHALL display per-sector result rows with status, key labels, and report path when available
- **AND** it SHALL display final success, skipped, and failed counts
- **AND** it SHALL NOT print generated report content by default

#### Scenario: Batch group update shows group and member refresh summaries
- **WHEN** a user runs `wchat ai sector-trends groups update --all`
- **THEN** the system SHALL display per-group result rows with status, member refresh summary, key group labels, and group report path when available
- **AND** it SHALL display final group success, skipped, and failed counts
- **AND** it SHALL display aggregate member refresh success and failure counts when member refresh is enabled
- **AND** it SHALL NOT print generated group report content by default

#### Scenario: Existing report skip shows existing output path
- **WHEN** a trend generation command skips because a target date report already exists and force is not enabled
- **THEN** the system SHALL display that the report was skipped
- **AND** it SHALL display the existing report path when available

#### Scenario: Report content is viewed explicitly
- **WHEN** a user uses a show command or an explicit content-viewing option
- **THEN** the system MAY display report content or a bounded preview
- **AND** generation commands SHALL remain path-and-metadata focused by default
