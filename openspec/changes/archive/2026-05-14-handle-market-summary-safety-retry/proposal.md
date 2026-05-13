## Why

`wchat ai market-summary` can currently fail after the main summary is already generated when the secondary strategy-enhancement LLM call is rejected by provider-side content safety checks. This loses an otherwise usable market summary and makes retry behavior opaque because the sanitized prompt is retried unchanged until the command fails.

## What Changes

- Add a degraded-success path for market-summary strategy enhancement: if only the secondary enhancement call is blocked by content safety, preserve and save the initial summary instead of failing the whole command.
- Constrain strategy-enhancement inputs so they rely on structured market evidence and summary-level context rather than resubmitting full generated prose and raw sensitive titles.
- Improve content-safety retry handling so logs identify the failed generation stage and do not repeatedly retry an unchanged prompt without a clearer fallback path.
- Preserve factual market evidence such as indices, turnover, breadth, sectors, stock samples, and source availability when sanitizing prompts.
- Require conservative output semantics when sanitized or reduced evidence is insufficient, using observation / waiting-for-confirmation language instead of fabricated event conclusions.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `market-summary`: Market summary generation shall gracefully degrade when secondary strategy enhancement is blocked by content safety review.
- `ai-processing`: AI prompt retry and sanitization behavior shall support stage-aware handling for content safety failures without distorting structured factual evidence.

## Impact

- Affected code:
  - `src/services/ai_processor.py`
  - market-summary structure tests around strategy enhancement and prompt construction
  - AI processor tests around content-safety retry and sanitization
- Affected CLI behavior:
  - `wchat ai market-summary` should complete and save the first-pass summary when strategy enhancement is blocked.
  - Logs should show whether the blocked call occurred during initial summary generation or strategy enhancement.
- No database schema, public CLI option, or external dependency changes are expected.
