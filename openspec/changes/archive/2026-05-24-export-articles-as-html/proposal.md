## Why

The current public-account export writes each article as Markdown, but WeChat articles are rich HTML documents with nested sections, inline styles, images, and layout blocks that degrade when converted to Markdown. For reading and archiving public-account articles locally, HTML is a better default because it preserves the stored article body and avoids losing visual structure during conversion.

## What Changes

- Change `wchat export <mp_id>` from Markdown export to HTML export.
- Export one `.html` file per article under the existing `output/export_articles/<mp_id>/` directory.
- Replace Markdown generation with an HTML document template that includes:
  - document metadata and UTF-8 charset
  - article title
  - publish time when available
  - original article URL when available
  - cover image when available
  - summary when available
  - stored article HTML content as the body
  - lightweight CSS for readable local viewing and responsive images
- Change generated filenames from `YYYY-MM-DD_<title>.md` to `YYYY-MM-DD_<title>.html`.
- Preserve existing incremental export behavior and `--force` behavior.
- Do not add other export formats such as Markdown, JSONL, PDF, EPUB, or multi-format switches.
- Existing `.md` files are not migrated or deleted in incremental mode; `--force` continues to clear and rebuild the target export directory.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `html-to-markdown`: Replace the current export-flow requirement that writes Markdown files with an HTML export flow. The standalone `html_to_markdown()` utility remains available for other uses, but `wchat export <mp_id>` no longer uses it as the article export body path.

## Impact

- Affected code:
  - `src/cli/article.py`
  - tests that assert `.md` filenames or Markdown content from `wchat export`
- Affected specs:
  - `openspec/specs/html-to-markdown/spec.md`
- No database schema changes.
- No new runtime dependency.
- No change to article fetching, RSS attribution, AI summaries, or stored article content.
- User-visible behavior change: exported article files become `.html` instead of `.md`.
