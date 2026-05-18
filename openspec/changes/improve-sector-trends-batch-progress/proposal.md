## Why

`wchat ai sector-trends update --all` can run for a long time while repairing shared evidence, preparing sector evidence, calling AI, and saving reports. The current CLI shows only a generic spinner until the full batch finishes, so users cannot tell which sector is running, whether work is stuck, or how to retry failures.

## What Changes

- Add structured progress reporting for `sector-trends update --all`, including batch start/done, shared repair, per-sector start, per-sector stages, API retries, per-sector completion, and failures.
- Render batch progress in the CLI as live, readable lines that show the current sector index, sector name, stage, result, elapsed time, and final summary.
- Surface AI retry diagnostics in normal output without exposing sensitive configuration details; include extra provider/model/host details only where a verbose mode is available.
- Make `--skip-preparation` effective in `--all` mode so batch behavior matches the single-sector option.
- Preserve the existing final summary table and non-batch `--sector` behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sector-trend-tracking`: strengthen the batch update requirement so `update --all` reports real-time progress, retry events, per-sector status, and honors batch preparation options.

## Impact

- `src/services/sector_trend_service.py`: batch update progress event model, callback support, per-sector stage bridging, AI retry bridging, and `skip_preparation` support.
- `src/cli/sector_trends.py`: `update --all` rendering, optional verbosity handling if needed, and summary output adjustments.
- `tests/test_sector_trends.py` or focused new tests: service progress event sequence, CLI rendering, `--skip-preparation` propagation, and retry visibility.
- No database schema changes and no breaking command syntax changes are expected.
