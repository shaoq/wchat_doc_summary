## 1. Data Model

- [x] 1.1 Add `SectorGroup`, `SectorGroupMember`, `SectorGroupSuggestion`, `SectorGroupSuggestionMember`, and `SectorGroupTrendSummary` models to `src/models/schema.py`
- [x] 1.2 Add database initialization for new sector group tables in `src/storage/database.py`
- [x] 1.3 Add uniqueness constraints for group names, group-sector memberships, and duplicate pending suggestion relationships
- [x] 1.4 Add indexes for group status, suggestion status/type, target group, member sector, and group trend report date

## 2. Group Service

- [x] 2.1 Implement sector group CRUD operations for create, list, resolve by name/alias, and show details
- [x] 2.2 Implement manual member add/update behavior with relation type, weight, source, and confidence metadata
- [x] 2.3 Implement group detail loading with member sector status, latest seen date, latest sector update date, and latest member freshness metadata
- [x] 2.4 Ensure adding an existing group-sector membership updates metadata instead of creating duplicates

## 3. Suggestion Engine

- [x] 3.1 Implement suggestion generation input collection from tracked/candidate sectors, existing groups, existing members, and recent evidence
- [x] 3.2 Implement existing-group matching using group names, aliases, keywords, descriptions, member overlap, and recent co-occurrence signals
- [x] 3.3 Generate `new_group`, `add_members`, and `update_members` suggestions with reasons, confidence, and evidence JSON
- [x] 3.4 Prefer `add_members` for matched existing groups before creating `new_group` suggestions
- [x] 3.5 Exclude ignored sectors from suggestions by default and exclude inactive sectors unless explicitly included
- [x] 3.6 Refresh equivalent pending suggestions instead of creating duplicates
- [x] 3.7 Suppress add-member suggestions for already confirmed memberships

## 4. Suggestion Review

- [x] 4.1 Implement listing and filtering pending/accepted/ignored suggestions
- [x] 4.2 Implement accepting full suggestions, including creating groups and memberships as needed
- [x] 4.3 Implement accepting selected suggestion members via include/exclude options
- [x] 4.4 Promote candidate sectors to tracked by default when accepted into a group
- [x] 4.5 Implement keep-status acceptance behavior for candidate members
- [x] 4.6 Implement ignoring suggestions and preventing repeated display of unchanged ignored relationships

## 5. Group Trend Updates

- [x] 5.1 Implement group evidence collection from confirmed members, latest sector summaries, and recent member-level raw evidence
- [x] 5.2 Implement member freshness calculation for target date, stale summaries, missing summaries, and candidate members
- [x] 5.3 Add group-level AI prompt template focused on resonance, diffusion, rotation, core/catch-up structure, and retreat risk
- [x] 5.4 Implement group trend report generation and persistence separate from single-sector reports
- [x] 5.5 Implement default group update that refreshes confirmed tracked members without target-date reports before group report generation
- [x] 5.6 Implement `no-refresh-members` behavior to generate group reports from existing summaries and raw evidence only
- [x] 5.7 Implement force refresh behavior for all eligible tracked group members before group report generation
- [x] 5.8 Ensure candidate members are not refreshed by default and are marked clearly in group output

## 6. CLI

- [x] 6.1 Add and register `wchat ai sector-trends groups` command group
- [x] 6.2 Implement `groups ls` with status, member count, latest update date, and pending suggestion count
- [x] 6.3 Implement `groups show --group <name>` for metadata, members, relation types, status, and freshness
- [x] 6.4 Implement `groups create` and `groups add` for manual group and member management
- [x] 6.5 Implement `groups suggest --days N` for pending suggestion generation
- [x] 6.6 Implement `groups suggestions` for suggestion review
- [x] 6.7 Implement `groups accept` and `groups ignore` with partial accept and keep-status options
- [x] 6.8 Implement `groups update --group <name>` with refresh options and summary output
- [x] 6.9 Implement `groups history --group <name>` and latest group report viewing
- [x] 6.10 Add shared stage-rendering helpers for sector and group trend generation, following the `market-summary` header/conclusion/detail style
- [x] 6.11 Update single-sector `update --sector` output to show setup, evidence collection, AI generation, save stages, key labels, elapsed time, and report path without printing report content
- [x] 6.12 Update single-group `groups update --group` output to show member refresh plan, refresh results, evidence collection, AI generation, save stages, key labels, elapsed time, and group report path without printing report content
- [x] 6.13 Update `update --all` and `groups update --all` output to show compact per-item rows and final success/skipped/failed/member-refresh counts without printing report content
- [x] 6.14 Ensure skipped existing reports display the existing report path when available

## 7. Tests

- [x] 7.1 Add model and database initialization tests for all new tables and constraints
- [x] 7.2 Add service tests for group CRUD and member metadata updates
- [x] 7.3 Add suggestion generation tests for new-group, add-members, update-members, duplicate suppression, and ignored-sector exclusion
- [x] 7.4 Add suggestion acceptance tests for full accept, partial accept, ignored suggestions, candidate promotion, and keep-status behavior
- [x] 7.5 Add group update tests for default missing-member refresh, no-refresh-members, force refresh, and candidate member handling
- [x] 7.6 Add CLI registration and command output tests for group commands
- [x] 7.7 Add AI prompt/label extraction tests for group trend summaries
- [x] 7.8 Add CLI output tests verifying stage headers, member refresh summaries, generated file paths, skipped existing paths, and no default report body output

## 8. Verification

- [x] 8.1 Run focused sector group test suite
- [x] 8.2 Run existing sector trend tests to confirm single-sector behavior remains unchanged
- [x] 8.3 Run relevant CLI command tests
- [x] 8.4 Run OpenSpec validation/status checks for `add-sector-group-mapping`
