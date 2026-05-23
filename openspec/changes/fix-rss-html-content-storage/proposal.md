## Why

RSS-backed articles can be persisted with `Article.content` empty while the full HTML article body is stored in `Article.summary`. HTML export then escapes that summary as text, so users see literal HTML tags instead of rendered article content. This breaks local article reading and indicates the RSS import pipeline is mixing up body content and textual summary fields.

## What Changes

- Fix RSS article persistence so feed-provided HTML body is stored in `Article.content` even when WeChat page parsing cannot extract a content fragment.
- Stop treating RSS feed HTML body as a textual `Article.summary`.
- Add a defensive HTML export fallback for historical records where `content` is empty but `summary` clearly contains HTML body content.
- Provide a controlled repair path for existing RSS records that have `content` empty and HTML stored in `summary`.
- Preserve normal AI-generated/text summaries when they are plain text summaries, not full HTML bodies.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `article-fetcher`: RSS-backed article import must store HTML body content in `Article.content` and avoid placing full HTML body content into `Article.summary`.
- `html-to-markdown`: HTML article export must render historical RSS body HTML even when it was previously stored in `Article.summary`.

## Impact

- Affected code:
  - `src/services/fetcher.py`
  - `src/api/providers/rss_provider.py` if RSS normalization needs clearer summary/content separation
  - `src/cli/article.py`
  - optional repair/backfill command or service path
- Affected tests:
  - RSS fetcher content-mode tests
  - HTML export tests
  - repair/backfill tests for historical RSS records
- Database schema does not need to change.
- Existing rows may be updated by the controlled repair path.
- No changes to RSS source configuration, RSS attribution, or export file format.
