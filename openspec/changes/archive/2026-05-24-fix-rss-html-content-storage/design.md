## Context

RSS feed entries can provide article body HTML in fields such as `content`, `content:encoded`, `summary`, or `description`. The current normalization path may use the same HTML value as both `ProviderArticle.summary` and `ProviderArticle.content_html`. Later, `_fetch_and_save_rss_article()` parses `content_html` with `parse_article_html()`. For RSS fragments that are not full WeChat article pages, parsing can return no `content`; the article is then saved with `Article.content` empty while the full HTML fragment remains in `Article.summary`.

The HTML export builder correctly escapes `Article.summary` as metadata. That exposes the persistence issue: historical RSS articles render literal tags because body HTML was stored in the summary field.

Observed local data shape:
- RSS articles have `provider='rss'`
- many have `Article.content` empty
- their `Article.summary` starts with HTML tags and contains the full article body

## Goals / Non-Goals

**Goals:**
- Ensure new RSS articles store renderable body HTML in `Article.content`.
- Avoid storing full RSS HTML body fragments in `Article.summary`.
- Keep plain text summaries as summaries when they are actually summaries.
- Allow HTML export to render historical RSS articles whose body HTML was previously stored in `summary`.
- Provide a controlled repair path for existing affected rows.

**Non-Goals:**
- No database schema changes.
- No image mirroring or asset downloading.
- No change to RSS source configuration or attribution policy.
- No change to the HTML export file format.
- No broad reparse of every historical non-RSS article.

## Decisions

1. Separate RSS body HTML from summary during normalization.

   `RSSProvider._normalize_entry()` should distinguish:
   - body HTML candidate: `entry.content[*].value`, `content:encoded`, or HTML-rich `summary/description` when no better body field exists
   - textual summary candidate: short plain text summary, if available

   If `summary/description` is used as the body fallback because it contains HTML, it should not also be treated as a textual summary.

   Rationale: the same HTML fragment should not be saved into both body and summary fields.

2. Fallback to feed HTML when page parser returns no content.

   In `_fetch_and_save_rss_article()`, after `_resolve_rss_content()` returns `html`, use `parse_article_html(html)` as a best-effort parser. If `parsed.get("content")` is empty, store the original `html` in `Article.content`.

   Rationale: RSS content is often already a body fragment, not a full WeChat page. Failing to parse the wrapper should not discard the fragment.

3. Keep summary plain text only.

   When persisting RSS articles, `Article.summary` should receive a plain text summary only when the normalized summary is not an HTML body fragment. A simple helper can detect likely HTML with patterns such as leading `<`, common tags, or escaped tag markers. If a candidate is HTML-rich, do not store it as summary.

   Rationale: export and UI can safely escape summary as user-facing text if the field contains text, not document markup.

4. Add HTML export fallback for historical affected rows.

   `build_article_html()` should derive body HTML as:
   - `Article.content` when present
   - otherwise, for RSS-like historical records, `Article.summary` when it looks like HTML body content
   - otherwise empty body

   When summary is used as fallback body, the summary metadata block should not render that same value as escaped summary.

   Rationale: this immediately fixes rendering for existing affected rows without requiring users to run a repair first. It is a defensive compatibility layer, not the primary storage model.

5. Provide a controlled repair path.

   Implement a repair function or CLI-accessible maintenance path that updates affected rows:
   - scope: `provider='rss'`
   - condition: `content IS NULL OR content=''`
   - condition: `summary` looks like HTML body content
   - action: copy `summary` to `content`
   - action: clear `summary` or leave it null unless a plain text summary can be derived safely

   The repair should report candidate count and updated count. If implemented as a command, prefer an explicit command name and optional dry-run.

   Rationale: defensive export fallback is useful, but corrected storage prevents the same bug from surfacing in other content consumers.

## Risks / Trade-offs

- HTML detection may misclassify a short text summary containing angle brackets → Use conservative checks: provider must be RSS for repair, and fallback should require clear tag-like structure.
- Clearing historical summary loses the misplaced HTML copy → It is copied to `content` first; preserving duplicate body in summary is more harmful for export/UI.
- Some RSS summaries may intentionally be HTML snippets but not full bodies → If the feed provides no separate content field, using the HTML summary as body is acceptable because it is the best available display content.
- Export fallback can mask incomplete repair → Keep tests for both new persistence and historical fallback so the primary fix is not skipped.

## Migration Plan

1. Ship the new RSS persistence behavior so newly fetched RSS articles populate `Article.content`.
2. Add export fallback so affected existing rows render correctly immediately.
3. Add and run the controlled repair path to migrate existing affected RSS rows from `summary` to `content`.
4. Regenerate HTML exports with `wchat export <mp_id> --force` or `wchat export --all --force` after repair if already-exported files contain escaped tags.

## Open Questions

- Whether the repair command should derive a plain text summary from the HTML body is intentionally left out of the first version. The safer first repair is to move body HTML to `content` and clear misplaced summary.
