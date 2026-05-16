## 1. Taxonomy Definition

- [ ] 1.1 Add a reusable sector trend stage taxonomy definition covering every supported single-sector `trend_status`.
- [ ] 1.2 Add a reusable sector group stage taxonomy definition covering every supported group `trend_status`.
- [ ] 1.3 Define shared evidence dimensions and allowed-stage restrictions for sparse, stale, or missing evidence.
- [ ] 1.4 Define stage transition constraints for first reports, continuation, strengthening, divergence, and retreat.

## 2. Prompt Integration

- [ ] 2.1 Update the sector trend prompt/template to include sector stage definitions and sparse-evidence downgrade rules.
- [ ] 2.2 Update the group trend prompt/template to include group stage definitions, member-state constraints, and freshness downgrade rules.
- [ ] 2.3 Ensure prompt wording treats `trend_status` as descriptive trend state rather than recommendation output.

## 3. Service Guardrails

- [ ] 3.1 Add sector label validation that downgrades obviously invalid stage choices based on evidence sufficiency and prior-state context.
- [ ] 3.2 Add group label validation that downgrades obviously invalid stage choices based on member freshness and member sector states.
- [ ] 3.3 Preserve existing enum values, persisted fields, and output paths without requiring a database migration.

## 4. Tests

- [ ] 4.1 Add tests for sector sparse-evidence downgrade behavior.
- [ ] 4.2 Add tests for sector stage transition constraints such as first-report and `主线加强` cases.
- [ ] 4.3 Add tests for group member freshness downgrade behavior.
- [ ] 4.4 Add tests for group-member consistency constraints such as `主线共振`, `主线扩散`, and `高位退潮`.
- [ ] 4.5 Add prompt/template tests verifying that stage definitions are included.

## 5. Verification

- [ ] 5.1 Run targeted sector trend and group trend test suites.
- [ ] 5.2 Run OpenSpec validation/status checks for `add-trend-stage-taxonomy`.
- [ ] 5.3 Review generated labels in representative report fixtures or test doubles to confirm taxonomy-constrained output.
