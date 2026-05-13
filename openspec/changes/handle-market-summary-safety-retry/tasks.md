## 1. Safety Retry Plumbing

- [ ] 1.1 Add stage context to AI LLM call handling so content-safety logs identify the failed operation.
- [ ] 1.2 Preserve existing retry semantics while ensuring repeated safety failures do not imply additional sanitization after the first sanitized retry.
- [ ] 1.3 Add or update tests for content-safety detection, stage-aware logging, and final error preservation.

## 2. Market Summary Fallback

- [ ] 2.1 Wrap strategy-enhancement generation so content-safety failure returns the first-pass summary instead of failing the command.
- [ ] 2.2 Ensure initial full-summary content-safety failure remains fatal when no first-pass summary exists.
- [ ] 2.3 Add tests covering successful first-pass summary plus safety-blocked strategy enhancement.

## 3. Evidence-Bound Prompt Reduction

- [ ] 3.1 Refactor strategy-enhancement prompt construction to use structured strategy evidence and concise prior context instead of full summary prose where practical.
- [ ] 3.2 Ensure sanitization preserves structured market facts including indices, turnover, breadth, sectors, stock samples, global context status, and data gaps.
- [ ] 3.3 Add tests verifying risky event/title text can be removed or masked without changing structured market evidence.

## 4. Verification

- [ ] 4.1 Run focused market-summary structure tests.
- [ ] 4.2 Run focused AI processor tests for retry and sanitization behavior.
- [ ] 4.3 Run OpenSpec validation for `handle-market-summary-safety-retry`.
