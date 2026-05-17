## Why

`wchat ai market-summary` currently treats公众号文章 as a lightweight title/summary supplement, even though many selected articles are already market reviews or next-day strategy notes. This causes historical and current summaries to miss structured viewpoints about mainlines, sector rotation, sentiment, watchlists, and risks that are present in the article corpus.

## What Changes

- Add automatic preparation of structured market article evidence for articles in the market-summary article window.
- Upgrade market-summary article selection from raw publish-time ordering to relevance-aware candidate selection using article content, title, summary, feed metadata, and article type.
- Reuse existing article-processing persistence where possible so generated evidence can be cached, replayed, refreshed, and audited.
- Inject structured article viewpoints into the market-summary prompt and strategy-enhancement prompt instead of only listing article titles and short summaries.
- Preserve conservative evidence semantics:公众号文章 SHALL be treated as secondary viewpoint evidence and SHALL NOT override missing or contradictory market facts.
- Make historical `wchat ai market-summary --date <date> --force` automatically backfill missing local article evidence for that target date when local historical articles are available.
- Keep offline behavior local-only: offline runs SHALL use existing local article evidence and SHALL NOT fetch new articles; whether to call LLM for missing evidence must be explicitly controlled by the implementation contract.
- Persist enough source diagnostics so users can see how many articles were found, prepared, selected, skipped, or degraded.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `market-summary`: Consume structured公众号 article evidence as a dedicated summary input, including historical replay and source diagnostics.
- `ai-processing`: Add a reusable article-processing task for market article evidence extraction and caching.

## Impact

- Affected code:
  - `src/cli/ai.py`
  - `src/services/market_analyzer.py`
  - `src/services/ai_processor.py`
  - Article-processing persistence through `ArticleProcessing`
  - Market summary prompt template `templates/market_summary.md`
- Affected outputs:
  - `output/market_summaries/<date>.md`
  - `market_summaries.data_sources`
  - CLI stage-2 source diagnostics for article evidence
- Tests:
  - Market-summary CLI flow
  - News ingestion and article window selection
  - AI prompt construction and strategy enhancement
  - Article evidence extraction, caching, force refresh, and degradation paths
