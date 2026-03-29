## 1. Preflight And Flow Ordering

- [x] 1.1 Move `market-summary` local preflight checks such as date parsing ahead of `AIProcessor` initialization
- [x] 1.2 Add CLI coverage proving invalid local input exits before any AI-dependent component is initialized

## 2. News Stage Semantics

- [x] 2.1 Refine news aggregation result handling so partial source failures are surfaced as degraded execution rather than full success
- [x] 2.2 Update `market-summary` CLI output and related tests to distinguish successful, degraded, and failed news-stage outcomes

## 3. Summary Persistence Consistency

- [x] 3.1 Refine `save_summary()` so command completion only reports success after both database persistence and Markdown file persistence succeed
- [x] 3.2 Add regression coverage for persistence failure paths to prevent silent partial-success states

## 4. Market Data Strategy Cleanup

- [x] 4.1 Consolidate `market-summary` market-data strategy usage around a single execution path to reduce duplicated cache/refresh semantics
- [x] 4.2 Update targeted tests to confirm offline, cache, and force-refresh behavior still match the documented command semantics
