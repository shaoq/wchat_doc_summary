## Context

`AIProcessor.generate_market_summary()` performs a first LLM call to create the full market summary. If the generated sixth section is too weak, it performs a second strategy-enhancement call and merges the returned section back into the summary.

The current retry path in `_call_api()` treats provider content-safety rejection as a generic retry after one prompt sanitization pass. If the sanitized prompt still triggers the provider, the same prompt is retried until the command fails. For market summaries this is especially costly because the first-pass summary may already be usable, but the secondary enhancement failure prevents saving it.

The fix should make the market-summary command resilient without weakening factual accuracy. Sanitization must not rewrite structured market facts such as index moves, turnover, breadth, sector names, stock samples, or source availability.

## Goals / Non-Goals

**Goals:**

- Preserve and save the first-pass market summary when only strategy enhancement is blocked by content safety.
- Make content-safety failures stage-aware enough to distinguish initial summary generation from optional strategy enhancement.
- Reduce the strategy-enhancement prompt surface by using structured evidence and concise context instead of full generated prose and raw event-heavy titles.
- Keep sanitized or reduced-evidence output conservative and explicitly evidence-bounded.
- Add focused tests for fallback behavior, prompt construction, and sanitization boundaries.

**Non-Goals:**

- Do not bypass, disable, or obscure provider safety controls.
- Do not add new CLI flags or database schema.
- Do not change market data collection, news fetching, or cache behavior.
- Do not guarantee that initial summary generation can succeed when the whole input is rejected by the provider.

## Decisions

1. Treat strategy enhancement as optional enrichment.

   If the first-pass summary succeeds and the second enhancement call fails due to content safety, return the first-pass summary and log a warning. This preserves the highest-fidelity successful output already available. Alternative considered: retry full summary generation with heavily sanitized input. That risks losing more evidence and makes the final report less traceable.

2. Add call-stage context to LLM invocation paths.

   `_call_api()` or its call sites should be able to identify whether the failing request is initial summary generation or strategy enhancement. The stage label is for logging and fallback control; it should not alter model behavior by itself.

3. Reduce enhancement prompt context rather than resubmitting full summary prose.

   The enhancement prompt should carry only the information needed to write the sixth section: structured strategy evidence, data gaps, and a compact digest of earlier section conclusions if needed. It should avoid full raw titles or full generated prose when equivalent structured evidence is available.

4. Keep sanitization evidence-preserving.

   Sanitization may remove or mask risky free-text titles and event descriptions, but must preserve numeric and structured market facts. When an event/title is removed, the prompt should retain source availability and data-gap semantics so the model can say that event evidence is insufficient.

5. Prefer conservative strategy wording under reduced evidence.

   When sanitization or prompt reduction removes event-level evidence, the strategy section must use observation / waiting-for-confirmation / no-judgment language for that evidence class. The system must not ask the model to infer a specific catalyst from missing text.

## Risks / Trade-offs

- Reduced enhancement context may produce a less detailed sixth section → Mitigate by preserving structured evidence and only reducing raw prose/event text.
- Strategy enhancement fallback may leave a weaker sixth section in rare cases → Mitigate by saving the usable first-pass summary and logging the degraded path.
- Over-broad sanitization can remove useful event detail → Mitigate with tests that verify market facts remain intact and event loss is represented as insufficient evidence.
- Initial summary generation can still fail if the provider rejects the primary prompt → This change only guarantees graceful fallback after a successful first-pass summary.
