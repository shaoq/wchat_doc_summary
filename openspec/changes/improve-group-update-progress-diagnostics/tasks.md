## 1. Progress Event Model

- [ ] 1.1 Define a lightweight group update progress event structure with type, group, member, stage, retry, error, timing, labels, and output path fields
- [ ] 1.2 Add progress callback plumbing to `update_group_trend` without changing existing return behavior
- [ ] 1.3 Add progress callback plumbing to `update_all_group_trends` for batch start, group start, group completion, group failure, and batch completion
- [ ] 1.4 Ensure services run unchanged when no progress callback is supplied

## 2. Member and AI Diagnostics

- [ ] 2.1 Emit member refresh start, skip, success, failure, and timing events
- [ ] 2.2 Capture structured member refresh failure details including group name, member name, task type, error summary, retryable flag, and attempts when available
- [ ] 2.3 Surface group summary generation start, retry, success, failure, and timing events
- [ ] 2.4 Add safe API retry diagnostic context for sector-trend and sector-group-trend calls
- [ ] 2.5 Sanitize diagnostics so API keys, authorization headers, full prompts, and full request headers are never printed

## 3. CLI Rendering

- [ ] 3.1 Add `--verbose` and `--quiet` options to `wchat ai sector-trends groups update`
- [ ] 3.2 Render batch start context including trade date, target count, lookback window, force mode, member refresh mode, and continue-on-error mode
- [ ] 3.3 Render current group progress with `[i/N] group_name` and current stage
- [ ] 3.4 Render per-group completion rows with action, member refresh summary, labels, report path, elapsed time, and error summary
- [ ] 3.5 Render final batch summary with counts, member refresh totals, failure details, retry commands, and total elapsed time
- [ ] 3.6 Implement verbose rendering for member-level refresh details, retry events, skip reasons, safe provider/model metadata, and stage timings
- [ ] 3.7 Implement quiet rendering that suppresses live details but keeps final counts and failure summaries

## 4. Recovery Guidance

- [ ] 4.1 Generate retry command suggestions for member refresh failures
- [ ] 4.2 Generate retry command suggestions for group summary failures
- [ ] 4.3 Include partial-success notes when member refresh fails but group update continues
- [ ] 4.4 Include continue-on-error behavior in final summary when failures occur

## 5. Tests

- [ ] 5.1 Add service tests verifying progress callback events for batch start, group start, stage changes, group completion, and batch completion
- [ ] 5.2 Add service tests verifying member refresh event emission for success, skip, failure, and retry when simulated
- [ ] 5.3 Add CLI tests for default `groups update --all` progress output
- [ ] 5.4 Add CLI tests for `--verbose` retry diagnostics and safe metadata display
- [ ] 5.5 Add CLI tests for `--quiet` final summary behavior
- [ ] 5.6 Add tests proving sensitive API data is not printed in diagnostics
- [ ] 5.7 Add tests for suggested retry commands after member refresh and group summary failures

## 6. Verification

- [ ] 6.1 Run focused sector group service tests
- [ ] 6.2 Run relevant CLI flow tests
- [ ] 6.3 Run OpenSpec validation/status checks for `improve-group-update-progress-diagnostics`
- [ ] 6.4 Run GitNexus impact analysis before editing update service symbols during implementation
- [ ] 6.5 Run GitNexus detect-changes before committing implementation changes
