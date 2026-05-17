## 1. Evidence Preparation Core

- [x] 1.1 Add shared evidence preparation data models for entity type, target date/window, confidence tier, evidence role, provenance, and diagnostics.
- [x] 1.2 Add an EvidencePreparationService that coordinates watch repair, sector identity signals, theme registry signals, accepted learned terms, and market proxy discovery.
- [x] 1.3 Implement confidence tier classification for high, medium, and low confidence preparation results.
- [x] 1.4 Ensure low-confidence preparation results are diagnostic-only and cannot satisfy trend promotion gates.
- [x] 1.5 Add unit tests for preparation result merging, confidence tier behavior, provenance, and diagnostics aggregation.

## 2. Market Evidence Roles

- [x] 2.1 Extend sector evidence collection to classify market rows as `exact_market`, `alias_market`, `proxy_market`, or `no_market`.
- [x] 2.2 Add exact-market matching for canonical sector identity.
- [x] 2.3 Add high-confidence alias-market matching from explicit aliases and accepted equivalent identities.
- [x] 2.4 Add proxy-market matching from theme members, group members, and prepared proxy candidates without merging sector identities.
- [x] 2.5 Persist market evidence role diagnostics in sector `evidence_json`.
- [x] 2.6 Add tests for exact, alias, proxy, no-market, and mixed-role evidence.

## 3. Sector Workflow Integration

- [x] 3.1 Run automatic evidence preparation after `sector-trends init` creates or promotes a tracked sector.
- [x] 3.2 Run automatic evidence preparation before single-sector `sector-trends update` collects evidence.
- [x] 3.3 Run shared window preparation plus per-sector preparation before batch `sector-trends update --all`.
- [x] 3.4 Add CLI output that summarizes automatic sector preparation actions and unresolved gaps.
- [x] 3.5 Preserve debug or skip controls for reproducing behavior without automatic preparation.
- [x] 3.6 Add CLI and service tests for init, single update, batch update, diagnostics, and skip mode.

## 4. Theme Registry Integration

- [x] 4.1 Feed built-in themes, user theme config, accepted learned terms, active group metadata, and ignored/noise terms into evidence preparation.
- [x] 4.2 Treat accepted learned terms as high-confidence theme signals when applicable.
- [x] 4.3 Treat pending theme suggestions as low or medium confidence only, never as accepted high-confidence terms.
- [x] 4.4 Exclude disabled, ignored, noise, and conflicting terms from alias or proxy creation.
- [x] 4.5 Add diagnostics showing theme source layer, matched terms, and skipped conflict/noise reasons.
- [x] 4.6 Add tests for accepted terms, pending suggestions, built-in theme members, user overrides, and noise exclusions.

## 5. Group Workflow Integration

- [x] 5.1 Run automatic member evidence preparation when a group member is added or updated.
- [x] 5.2 Run automatic member evidence preparation when group suggestions are accepted.
- [x] 5.3 Run group and member evidence preparation before single group updates.
- [x] 5.4 Run shared preparation plus group-specific preparation before batch group updates.
- [x] 5.5 Ensure preparation does not create formal group memberships or merge sectors solely from proxy evidence.
- [x] 5.6 Add CLI output summarizing prepared members, proxy-backed members, low-confidence ignored matches, and unresolved gaps.
- [x] 5.7 Add tests for manual add, accepted suggestions, single group update, batch group update, and identity boundary preservation.

## 6. Validation Inputs and Guardrails

- [x] 6.1 Update sector stage validation inputs to distinguish direct market evidence, high-confidence alias evidence, proxy evidence, and no usable market evidence.
- [x] 6.2 Require proxy-market evidence to have fresh watch or telegraph confirmation before it can support active sector stages.
- [x] 6.3 Update group stage validation inputs to include member evidence quality, source breadth, freshness, and proxy-backed member activity.
- [x] 6.4 Ensure final member `暂无趋势` labels do not automatically erase high-confidence multi-source member evidence for group validation.
- [x] 6.5 Ensure low-confidence or stale member evidence still downgrades multi-member group active stages.
- [x] 6.6 Ensure groups with multiple fresh active member labels are not downgraded solely because proxy evidence was not needed.
- [x] 6.7 Synchronize final validated sector labels across Markdown structured labels, database summaries, CLI output, and downstream consumers.
- [x] 6.8 Synchronize final validated group labels across Markdown structured labels, database summaries, CLI output, and matrix/history consumers.
- [x] 6.9 Persist raw label, final label, and validation reason diagnostics when validation changes a sector or group label.
- [x] 6.10 Add regression tests proving taxonomy remains conservative and proxy evidence does not over-promote weak sectors or groups.
- [x] 6.11 Add regression tests proving Markdown labels and database labels remain identical after validation downgrade or upgrade.

## 7. Persistence and Backfill Compatibility

- [x] 7.1 Decide whether proxy relationships and preparation diagnostics use existing JSON metadata or a dedicated table, then implement the chosen storage.
- [x] 7.2 Preserve existing `TrackedSector` and `SectorGroupMember` identity semantics during preparation.
- [x] 7.3 Ensure existing manual repair and theme management commands continue to work.
- [x] 7.4 Ensure automatic preparation never performs implicit network fetches for missing raw data.
- [x] 7.5 Add migration or compatibility tests for existing databases.

## 8. Verification

- [x] 8.1 Add focused tests for robot-like cases with no exact market row but strong watch/telegraph and proxy evidence.
- [x] 8.2 Add focused tests for new sector and new group defaults requiring no manual repair commands.
- [x] 8.3 Run targeted sector trend, group trend, theme registry, watch repair, and taxonomy tests.
- [x] 8.4 Run `openspec validate add-automatic-sector-evidence-preparation --strict`.
