## Context

`sector-trends update --all` currently delegates the full batch to `SectorTrendAnalyzer.update_all_sector_trends()` under a single Rich status spinner. The service returns useful final counts, but it does not expose batch lifecycle events, shared repair status, per-sector stage changes, or AI retry diagnostics to the CLI while the run is active.

The nearby `sector-trends groups update --all` flow already uses a structured progress event object and renders incremental CLI output. The sector batch flow should follow the same pattern while keeping the simpler sector-only semantics.

## Goals / Non-Goals

**Goals:**

- Give users clear real-time feedback for `wchat ai sector-trends update --all`.
- Show batch context, shared repair progress, current sector index/name, per-sector stages, retries, final per-sector status, and final counts.
- Keep the service usable outside the CLI by exposing structured progress events instead of printing from the service layer.
- Make `--skip-preparation` work in batch mode.
- Preserve existing single-sector behavior and final batch result shape.

**Non-Goals:**

- Do not change the report generation prompt, report content, or persisted schema.
- Do not add parallel sector updates; the batch remains sequential to preserve cost/rate-limit behavior.
- Do not introduce a new progress rendering dependency beyond existing Rich usage.
- Do not expose secrets, raw API keys, or full provider URLs in progress output.

## Decisions

### 1. Add a sector-specific progress event dataclass

Add `SectorUpdateProgressEvent` in `src/services/sector_trend_service.py` with fields for event type, sector name, sector index/total, stage, action, elapsed time, output path, labels, error, retry metadata, and batch context.

Rationale: sector batch events are similar to group events but not identical. A dedicated dataclass avoids overloading group-specific fields such as `group_name`, `member_name`, and member refresh counters.

Alternative considered: reuse `GroupUpdateProgressEvent`. This would reduce code but make semantics confusing and couple the sector service to group-specific concepts.

### 2. Extend batch update with optional progress callback

Extend `update_all_sector_trends()` with `progress_callback: Callable[[SectorUpdateProgressEvent], None] | None` and `skip_preparation: bool = False`.

The service emits:

- `batch_start` after selecting target sectors and resolving the trade date.
- `shared_repair_start`, `shared_repair_done`, or `shared_repair_failed` around batch-level CLS repair.
- `sector_start` before each sector.
- `sector_stage` for single-sector stages bridged from `update_sector_trend()`.
- `api_retry` when AI generation retries.
- `sector_done`, `sector_skipped`, or `sector_failed` after each sector.
- `batch_done` with aggregate counts and elapsed time.

Rationale: this keeps progress generation close to the execution flow and lets CLI/tests assert event order without parsing terminal output.

### 3. Bridge single-sector stage and AI retry callbacks

Keep the existing `update_sector_trend(progress_callback: Callable[[str, str], None] | None)` API for compatibility, but add optional `retry_callback` support or an internal bridge so AI retry events can be surfaced through the batch event callback.

Rationale: existing callers and tests use the simple `(stage, detail)` callback shape. Batch rendering needs richer retry metadata, but that should not force all callers to migrate immediately.

### 4. Render incremental CLI lines instead of one long status spinner

Replace the `update --all` `console.status()` wrapper with an event renderer in `src/cli/sector_trends.py`.

Default output should be concise:

```text
批量更新板块趋势
  交易日: 2026-05-18
  目标: 12 个 tracked 板块
  回看窗口: 10 天

共享修复: CLS 看盘板块归属...
  v 已完成 repaired=8 low_confidence=2 unmatched=1

[1/12] 半导体
  运行证据准备...
  收集板块证据...
  AI 生成板块趋势...
  v 已更新 主线延续 强 关注  耗时 38s
```

Retry lines should be visible but sanitized:

```text
  ! 重试 (1/3) API timeout
```

Rationale: line-based output is stable for long-running CLI work and easier to test than a constantly updating progress bar.

### 5. Preserve final result details

The current final counts and detail table remain available after `batch_done`. The renderer should include elapsed time and failed-sector retry suggestions where practical.

Rationale: real-time progress improves observability during execution, while the final table remains useful for post-run review.

## Risks / Trade-offs

- [Risk] More event types increase test surface. -> Mitigate with focused service tests for event sequence and CLI tests for representative output rather than exhaustive terminal snapshots.
- [Risk] Duplicating concepts from group progress can drift over time. -> Mitigate by mirroring naming conventions where sensible (`batch_start`, `api_retry`, `batch_done`) while keeping sector-specific fields explicit.
- [Risk] Retry diagnostics could leak configuration details. -> Mitigate by truncating errors and only exposing non-sensitive provider/model/host metadata in verbose output, never secrets or full URLs.
- [Risk] Existing tests may depend on exact result shapes. -> Mitigate by only adding optional fields/parameters and preserving existing return keys.

## Migration Plan

No data migration is required. Implementation can be deployed as a CLI/service change only. Rollback is reverting the progress event and CLI rendering changes; existing batch update semantics and output files remain unchanged.

## Open Questions

- Should `sector-trends update --all` add `--quiet` and `--verbose` options to match group update, or should this change only add default incremental output plus sanitized retry messages?
