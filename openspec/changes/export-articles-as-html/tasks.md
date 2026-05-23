## 1. Pre-Change Analysis

- [x] 1.1 Run GitNexus impact analysis for `build_article_markdown`, `build_export_filename`, and `export` before editing those symbols.
- [x] 1.2 Review existing tests that assert Markdown export behavior and identify required updates.

## 2. HTML Export Builder

- [x] 2.1 Replace or supersede `build_article_markdown()` with `build_article_html()` for the export flow.
- [x] 2.2 Build a complete standalone HTML document with doctype, lang, charset, viewport, title, body, and article wrapper.
- [x] 2.3 HTML-escape template metadata fields including title, summary, original URL, cover URL, and formatted publish time.
- [x] 2.4 Preserve `Article.content` as HTML inside the article body without calling `html_to_markdown()`.
- [x] 2.5 Add embedded CSS for readable width, typography, metadata, summary block, and responsive images.
- [x] 2.6 Ensure empty or missing article content still produces a valid HTML document.

## 3. Export Command Behavior

- [x] 3.1 Change export filenames from `.md` to `.html` while preserving date-prefix, sanitized-title, and collision handling.
- [x] 3.2 Update `wchat export <mp_id>` to write HTML content using the new builder.
- [x] 3.3 Preserve incremental skip behavior for existing `.html` files.
- [x] 3.4 Preserve `--force` behavior that clears and rebuilds the export directory.
- [x] 3.5 Update command help/docstring text from Markdown export to HTML export.

## 4. Tests

- [x] 4.1 Update builder tests to assert complete HTML document structure and escaped metadata.
- [x] 4.2 Add coverage that stored article HTML is preserved and `html_to_markdown()` is not used by the export body path.
- [x] 4.3 Add filename tests for `.html` extension and collision suffixes.
- [x] 4.4 Add export command coverage for incremental skip and forced rebuild behavior with HTML files.
- [x] 4.5 Keep standalone `html_to_markdown()` tests intact because the utility remains available.

## 5. Verification

- [x] 5.1 Run focused article export and HTML converter tests.
- [x] 5.2 Run OpenSpec status or validation checks for `export-articles-as-html`.
- [x] 5.3 Run `gitnexus_detect_changes()` before committing to confirm expected affected symbols and flows.
