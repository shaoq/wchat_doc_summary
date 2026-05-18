## 1. Service Progress Events

- [x] 1.1 Add `SectorUpdateProgressEvent` and progress callback typing in `src/services/sector_trend_service.py`
- [x] 1.2 Extend `update_all_sector_trends()` with optional `progress_callback` and `skip_preparation` parameters while preserving existing return keys
- [x] 1.3 Emit batch lifecycle events: `batch_start`, shared repair start/done/failed, and `batch_done`
- [x] 1.4 Emit per-sector lifecycle events: `sector_start`, stage updates, done/skipped/failed, elapsed time, output path, and labels
- [x] 1.5 Bridge `update_sector_trend()` stage callbacks into batch sector events
- [x] 1.6 Bridge AI retry diagnostics from `generate_sector_trend_summary()` into sanitized `api_retry` progress events

## 2. CLI Rendering

- [x] 2.1 Replace the `update --all` single status spinner with an event renderer in `src/cli/sector_trends.py`
- [x] 2.2 Render batch context before long-running work starts, including trade date, target count, lookback window, and force/preparation options
- [x] 2.3 Render shared repair progress and repair diagnostics without blocking later sector output
- [x] 2.4 Render per-sector index/name, active stages, retry messages, completion status, elapsed time, labels, and errors
- [x] 2.5 Preserve the final counts and per-sector summary table after batch completion
- [x] 2.6 Pass `skip_preparation` from the CLI to batch service execution

## 3. Tests

- [x] 3.1 Add service tests for batch progress event ordering and required batch context fields
- [x] 3.2 Add service tests for per-sector stage bridging and done/skipped/failed events
- [x] 3.3 Add tests proving `--skip-preparation` is honored in batch mode
- [x] 3.4 Add tests for sanitized AI retry progress events
- [x] 3.5 Add CLI tests covering representative `update --all` progress output and final summary
- [x] 3.6 Run focused sector trend and group progress tests to ensure related flows did not regress

## 4. Verification

- [x] 4.1 Run `openspec validate improve-sector-trends-batch-progress --strict`
- [x] 4.2 Run the relevant pytest targets for sector trend progress behavior
- [x] 4.3 Run `gitnexus_detect_changes()` before any commit in the implementation stage
