## 1. Theme Registry

- [x] 1.1 Define theme dictionary data structures for themes, members, aliases, disabled terms, noise terms, source layer, confidence, and metadata
- [x] 1.2 Move current built-in theme definitions behind a registry loader while preserving existing fallback behavior
- [x] 1.3 Add user configuration loading for `config/sector_group_themes.json` or the chosen local config path
- [x] 1.4 Merge built-in themes, user config, accepted learned terms, active group metadata, disabled terms, and noise terms with deterministic precedence
- [x] 1.5 Update `SectorGroupService.match_theme` and suggestion generation to use the merged registry

## 2. Persistence

- [x] 2.1 Add persistence for theme-term suggestions, including type, target theme, suggested theme, term, normalized key, status, confidence, reason, and evidence JSON
- [x] 2.2 Add persistence for accepted learned terms if accepted terms are stored separately from the user config
- [x] 2.3 Add database initialization or config write helpers for the chosen persistence model
- [x] 2.4 Ensure ignored theme-term suggestions suppress unchanged future suggestions
- [x] 2.5 Add backup-safe config write behavior if accepted suggestions update a JSON config file

## 3. Theme Dictionary CLI

- [x] 3.1 Add `wchat ai sector-trends groups themes` to list effective themes
- [x] 3.2 Add `groups themes show --theme <name>` to display members, aliases, source layers, disabled members, and learned terms
- [x] 3.3 Add `groups themes validate` to report duplicate terms, cross-theme conflicts, disabled conflicts, and noise-term conflicts
- [x] 3.4 Add manual `groups themes add/remove/ignore-term` commands for user-maintained terms and noise terms
- [x] 3.5 Keep all theme dictionary commands separate from formal sector group membership commands

## 4. Candidate Discovery

- [x] 4.1 Extract theme-term candidates from `market_sectors` within a lookback window
- [x] 4.2 Extract theme-term candidates from `cls_watch_data` titles, content, and structured sectors when available
- [x] 4.3 Extract theme-term candidates from stored market summaries and high-signal sections such as main line, strategy, and observation labels
- [x] 4.4 Extract candidate learning opportunities from accepted sector group suggestions and active group metadata
- [x] 4.5 Implement rule-based scoring with source weights, co-occurrence signals, existing-theme proximity, and noise penalties
- [x] 4.6 Filter low-evidence candidates before AI classification

## 5. AI Classification

- [x] 5.1 Add an AI prompt/template for theme-term classification with strict JSON output
- [x] 5.2 Implement classification actions: `add_to_existing_theme`, `create_theme`, `mark_noise`, and `ignore`
- [x] 5.3 Validate AI output against known candidate terms, known themes, confidence thresholds, and supported actions
- [x] 5.4 Fall back safely when AI fails, times out, returns invalid JSON, or returns low-confidence output
- [x] 5.5 Store AI reason and evidence references in pending theme-term suggestions

## 6. Suggestion Review and Learning

- [x] 6.1 Add `groups themes suggest --days N` to generate pending theme-term suggestions
- [x] 6.2 Add `groups themes suggestions` to review pending/accepted/ignored theme-term suggestions
- [x] 6.3 Add `groups themes accept <id>` to apply accepted suggestions to the effective dictionary
- [x] 6.4 Add `groups themes ignore <id>` to suppress unchanged low-quality suggestions
- [x] 6.5 Ensure accepted theme-term suggestions do not create formal `SectorGroupMember` records or promote `TrackedSector` status
- [x] 6.6 Use accepted learning results in subsequent `groups suggest` runs

## 7. Tests

- [x] 7.1 Add unit tests for theme registry merge precedence and noise-term overrides
- [x] 7.2 Add config loading and config validation tests
- [x] 7.3 Add candidate extraction tests for market sectors, CLS watch titles, market summaries, and accepted group suggestions
- [x] 7.4 Add rule scoring and low-evidence filtering tests
- [x] 7.5 Add AI classification tests for existing-theme mapping, new-theme creation, mark-noise, invalid JSON, unknown terms, and low confidence
- [x] 7.6 Add review/accept/ignore tests for theme-term suggestions
- [x] 7.7 Add CLI tests for theme list/show/validate/manual add/remove/suggest/suggestions/accept/ignore
- [x] 7.8 Add integration test proving accepted theme learning affects later `groups suggest` output

## 8. Verification

- [x] 8.1 Run focused sector group and theme learning test suites
- [x] 8.2 Run relevant sector trend and group suggestion regression tests
- [x] 8.3 Run OpenSpec validation/status checks for `add-sector-group-theme-learning`
- [x] 8.4 Run GitNexus impact analysis before editing service symbols during implementation
- [x] 8.5 Run GitNexus detect-changes before committing implementation changes
