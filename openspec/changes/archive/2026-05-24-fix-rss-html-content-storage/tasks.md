## 1. Pre-Change Analysis

- [x] 1.1 Run GitNexus impact analysis for `RSSProvider._normalize_entry`, `FetcherService._fetch_and_save_rss_article`, and `build_article_html` before editing.
- [x] 1.2 Inspect current RSS rows to confirm affected historical pattern and expected repair count.

## 2. RSS Content Classification

- [x] 2.1 Add a small helper to detect whether a string clearly contains HTML body content.
- [x] 2.2 Update RSS normalization so HTML body fallback values are not also exposed as textual summaries.
- [x] 2.3 Preserve plain text summaries when the feed provides a real summary.

## 3. New RSS Persistence Behavior

- [x] 3.1 Update `_fetch_and_save_rss_article()` to fallback to the original feed HTML when `parse_article_html()` returns empty content.
- [x] 3.2 Ensure RSS body HTML is saved to `Article.content`.
- [x] 3.3 Ensure full HTML body values are not saved to `Article.summary`.
- [x] 3.4 Preserve parsed title and cover extraction when available.

## 4. HTML Export Historical Fallback

- [x] 4.1 Update `build_article_html()` to use `Article.summary` as body HTML only for historical RSS-like rows with empty content and clear HTML body summary.
- [x] 4.2 Suppress the escaped summary metadata block when summary is used as body fallback.
- [x] 4.3 Keep plain text summaries escaped in the metadata block.

## 5. Historical Repair Path

- [x] 5.1 Implement a controlled repair function or maintenance CLI path for affected RSS rows.
- [x] 5.2 Scope repair to `provider='rss'`, empty `content`, and HTML-looking `summary`.
- [x] 5.3 Copy affected `summary` values into `content` and clear misplaced `summary`.
- [x] 5.4 Report matched and updated row counts.
- [x] 5.5 Add a dry-run mode if implemented as a user-facing command.

## 6. Tests

- [x] 6.1 Add RSS provider/fetcher tests for feed HTML fragments that cannot be parsed as full WeChat pages.
- [x] 6.2 Add tests proving HTML body content lands in `Article.content`, not `Article.summary`.
- [x] 6.3 Add tests proving plain text summaries remain summaries.
- [x] 6.4 Add HTML export tests for historical RSS summary-as-body fallback.
- [x] 6.5 Add repair tests for affected RSS rows and non-RSS rows.

## 7. Verification

- [x] 7.1 Run focused RSS fetcher and HTML export tests.
- [x] 7.2 Run OpenSpec status or validation checks for `fix-rss-html-content-storage`.
- [x] 7.3 Run `gitnexus_detect_changes()` before committing to confirm expected affected symbols and flows.
