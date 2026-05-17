## Why

Newly added sectors and sector groups can still produce `暂无趋势` or group-level data-missing reports when local evidence exists but is not connected to the new identity. Users should not have to manually run repairs or diagnose missing aliases, themes, and proxy market evidence after adding a sector or group member.

## What Changes

- Add an automatic sector evidence preparation pipeline that runs during sector initialization, group membership changes, and trend updates.
- Automatically repair CLS watch structured sector attribution for relevant windows and entities.
- Automatically derive and persist high-confidence aliases, theme links, and market proxy evidence candidates for new sectors and group members.
- Let trend updates consume exact, alias, and proxy market evidence with explicit evidence roles instead of treating all non-exact market gaps as absolute missing data.
- Let group trend validation consider member evidence quality and proxy-backed activity, not only each member's final `trend_status`.
- Add confidence tiers so high-confidence preparation can participate in trend judgement, medium-confidence evidence remains weak/diagnostic, and low-confidence matches do not promote trend stages.
- Ensure final validated labels are synchronized across persisted database metadata, Markdown report labels, CLI output, and downstream group validation.
- Add diagnostics and CLI feedback showing what evidence preparation ran automatically and what it changed.
- Keep manual repair and theme management commands available for review, correction, and historical backfills.

## Capabilities

### New Capabilities

### Modified Capabilities

- `sector-trend-tracking`: Sector init and update workflows SHALL automatically prepare evidence, including watch attribution, aliases, theme links, and market proxy evidence roles.
- `sector-group-tracking`: Group membership and group update workflows SHALL automatically prepare member evidence and use member evidence quality during group trend validation.
- `sector-group-theme-learning`: Theme dictionaries and accepted learned terms SHALL feed the automatic evidence preparation pipeline for new sectors and group members.

## Impact

- Affects `wchat ai sector-trends init`, `sector-trends update`, `sector-trends groups add`, and `sector-trends groups update`.
- Adds shared evidence-preparation service logic that coordinates CLS watch repair, sector identity matching, theme registry matching, and market proxy discovery.
- May add persistence for evidence-preparation diagnostics, aliases, proxy relationships, or attribution metadata.
- Updates trend-stage guardrail inputs to distinguish `exact_market`, `alias_market`, `proxy_market`, and `no_market` evidence roles without broadly relaxing validation.
- Updates report persistence so post-validation label changes cannot leave Markdown labels inconsistent with database labels.
- Adds tests for automatic preparation on new sectors, group members, date replay, confidence tiers, group validation, and no-implicit-network behavior.
