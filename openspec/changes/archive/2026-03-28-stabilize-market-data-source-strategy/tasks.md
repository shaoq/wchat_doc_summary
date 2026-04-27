## 1. Source Strategy Structure

- [x] 1.1 Introduce an explicit per-data-type source strategy structure for index, full-market snapshot, sector ranking, and limit-up data
- [x] 1.2 Refactor `FinanceClient` to route each market data type through its declared primary and fallback adapters while preserving the normalized contract

## 2. Priority Stability Improvements

- [x] 2.1 Keep the current dedicated index primary/fallback path and preserve shared snapshot reuse for volume and rise-fall statistics
- [x] 2.2 Change sector data to prefer a more stable dedicated sector adapter instead of relying primarily on the fragile realtime curl path
- [x] 2.3 Change limit-up data to prefer a dedicated limit-up pool adapter, with realtime snapshot filtering only as backup or补位 logic

## 3. Regression Coverage

- [x] 3.1 Add or update finance contract tests to verify per-type fallback behavior and normalized empty-value semantics
- [x] 3.2 Add coverage ensuring degraded source paths do not leak source-specific raw payload structures into `market-summary` stage 1 output
- [x] 3.3 Run targeted finance, cache, and market-summary tests to verify the source strategy remains stable across success and fallback paths
