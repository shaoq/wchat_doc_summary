## Why

Current sector and group trend reports constrain `trend_status` to fixed enum values, but the stages themselves are not fully defined. This prevents labels such as `低位启动`, `短线脉冲`, `主线延续`, and `主线共振` from being reliably compared across dates, sectors, and groups.

This change defines a convergent trend-stage taxonomy for both single sectors and sector groups, so future trend tables or matrices can display stable state transitions without relying on loosely interpreted AI labels.

## What Changes

- Define formal single-sector trend stages and their evidence requirements.
- Define formal sector-group trend stages and their group-structure requirements.
- Add shared evidence dimensions used by both stage systems, including evidence sufficiency, continuity, breadth, strength, freshness, prior-state context, and retreat signals.
- Add downgrade rules for sparse or stale evidence so insufficient data cannot produce overconfident stages.
- Add transition constraints so stages such as `主线加强` and `高位退潮` require valid prior context or sufficient window evidence.
- Add group-member consistency constraints so group stages must be compatible with member sector states and freshness.
- Update AI prompt expectations and service-level validation behavior to preserve the existing enum values while making their meanings stricter.
- No trading recommendation logic is added; the taxonomy only standardizes trend-state labeling.

## Capabilities

### New Capabilities

### Modified Capabilities

- `sector-trend-tracking`: Single-sector trend reports SHALL use defined stage semantics, evidence sufficiency rules, and transition constraints when producing `trend_status`.
- `sector-group-tracking`: Sector-group trend reports SHALL use defined group-stage semantics, member-state consistency rules, and sparse-member downgrade behavior when producing `trend_status`.

## Impact

- Affects sector trend generation prompts and label extraction/validation paths.
- Affects group trend generation prompts and label extraction/validation paths.
- Affects persisted `trend_status` semantics for future `SectorTrendSummary` and `SectorGroupTrendSummary` rows without requiring database schema changes.
- Affects tests around prompt content, label validation, sparse evidence downgrades, and group-member consistency.
- Does not change report storage paths, CLI command names, market data ingestion, or existing Markdown output locations.
