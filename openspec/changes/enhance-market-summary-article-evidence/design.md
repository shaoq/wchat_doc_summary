## Context

`market-summary` currently collects articles by publish-time window and passes only the first 10 formatted titles plus short summaries into the prompt. Many公众号 articles are post-close reviews or pre-market strategy notes that already summarize the day's mainline, sector rotation, sentiment, key stocks, and next-day risks. The current flow loses most of that value because it does not rank articles by market relevance, does not structure article viewpoints, and does not persist which article evidence was used.

The existing system already has:

- `Article` records with `feed_id`, `title`, `content`, `summary`, `provider`, and `publish_time`.
- `Feed` records with公众号 metadata and weight.
- `ArticleProcessing` for cached AI processing results.
- `MarketAnalyzer.collect_news_data()` as the market-summary news aggregation point.
- `AIProcessor.generate_market_summary()` and strategy enhancement prompt construction.

## Goals / Non-Goals

**Goals:**

- Automatically prepare structured market article evidence for `market-summary`.
- Make historical `--date <date> --force` runs backfill missing article evidence from local historical articles.
- Rank and select market-relevant review/strategy articles instead of using raw publish-time order only.
- Preserve article evidence as secondary viewpoint evidence that must not override contradictory or missing market facts.
- Reuse cached article evidence so reruns are deterministic and cost-aware.
- Expose diagnostics for article discovery, preparation, selection, skips, and degradation.

**Non-Goals:**

- Do not fetch missing historical公众号 articles during market-summary generation.
- Do not introduce a vector database or semantic search dependency in the first implementation.
- Do not replace CLS, market data, sector data, or limit-up data with article viewpoints.
- Do not require users to manually run `batch-summarize` before market-summary.
- Do not create a dedicated article-evidence table unless the implementation finds `ArticleProcessing` insufficient.

## Decisions

### Decision 1: Reuse `ArticleProcessing` for first-version evidence caching

Use a new processing task type, for example `market_article_evidence`, and store a JSON result containing structured article evidence. This avoids a migration-heavy first release while still allowing cached replay and force refresh.

Alternatives considered:

- New table `market_article_evidence`: better for querying but increases migration and schema complexity. Defer until evidence reuse across sector/group trends requires stronger indexing.
- Store only inside `market_summaries.data_sources`: insufficient because evidence must be reusable across reruns and historical dates.

### Decision 2: Split article handling into candidate selection and evidence preparation

The market-summary flow should first collect candidate articles for the existing article window, then select high-value candidates using deterministic signals before calling LLM extraction.

Candidate inputs should include:

- Article title, summary, content availability, publish time.
- Feed name, feed weight, provider.
- Keyword hits for post-close review, pre-market strategy, mainline, sector, sentiment, limit-up, consecutive-board, watchlist, and risk language.

This keeps LLM calls bounded and prevents low-relevance articles from consuming prompt budget.

### Decision 3: Extract structured viewpoint evidence, not raw prose

The extraction output should include article type, relevance, time role, mentioned sectors/stocks, mainline views, sentiment view, next-day watch items, risk points, and a short usable summary. The final market-summary prompt should consume this structured evidence rather than raw article bodies.

This makes article evidence auditable and lets prompts distinguish:

- Facts from market data.
- Event/news signals from CLS.
- Viewpoints from公众号 articles.

### Decision 4: Force and historical replay semantics

`wchat ai market-summary --date <date> --force` should:

- Recompute the article window for the target trade date.
- Use local articles already stored in that window.
- Generate missing `market_article_evidence`.
- Refresh existing evidence when the implementation's force policy marks it stale or when explicit force refresh is enabled.
- Regenerate the market summary using the newly prepared article evidence.

If no local articles exist for the historical window, the command must degrade explicitly instead of fabricating evidence.

### Decision 5: Offline semantics remain local-only

Offline mode must not fetch articles or CLS data. For LLM evidence preparation, the conservative default should be:

- Use existing cached `market_article_evidence` when present.
- Do not generate new evidence via LLM in offline mode unless a future explicit option enables local evidence preparation.
- Fall back to title/summary formatting when evidence is unavailable.

This preserves the current expectation that offline runs are replay-oriented and do not acquire new data.

### Decision 6: Article viewpoints cannot upgrade unsupported market conclusions

Prompt and validation language must treat article evidence as secondary. If article viewpoints mention a mainline but market data, CLS watch, telegraphs, sector movement, and limit-up evidence do not support it, the output must phrase the article signal as a viewpoint or watch item, not as confirmed market leadership.

## Risks / Trade-offs

- LLM cost and latency increase when many article evidence items are missing → Bound candidate count, cache results, and reuse existing evidence by default.
- Article authors may be biased or wrong → Label article evidence as viewpoint evidence and require cross-source confirmation for strong conclusions.
- Historical dates may lack local article content → Degrade with explicit diagnostics; do not auto-fetch or fabricate.
- Offline semantics may be misunderstood → CLI diagnostics should show whether article evidence was reused, skipped, or unavailable.
- JSON extraction can be malformed → Add robust parsing, schema normalization, and fallback to title/summary evidence.
- Feed metadata may be missing for older RSS articles → Treat feed metadata as optional and do not fail the summary.

## Migration Plan

1. Add the new article-processing task type and evidence JSON parser without changing existing article summary behavior.
2. Extend market-summary article collection to include optional feed metadata and evidence diagnostics.
3. Add automatic evidence preparation in the market-summary news aggregation path.
4. Update prompts to consume structured article evidence.
5. Add tests for current, historical, force, offline, malformed extraction, and no-local-article cases.
6. Rollback path: disable evidence preparation and fall back to the existing article title/summary formatter.

## Open Questions

- Should `--force` always refresh existing article evidence, or only generate missing evidence and refresh malformed/stale records?
- Should there be a future explicit CLI option such as `--refresh-article-evidence` for cost control?
- What is the initial maximum candidate count for LLM extraction: 10, 15, or 20?
