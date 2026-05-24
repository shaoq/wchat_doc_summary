## Context

The current article export command lives in `src/cli/article.py`. It validates a feed by `mp_id`, selects all articles for that feed, and writes one Markdown file per article to `output/export_articles/<mp_id>/`. The current body path calls `build_article_markdown()`, which writes Markdown metadata and converts stored `Article.content` HTML through `html_to_markdown()`.

This design changes only the public-account export output. It does not remove `html_to_markdown()` as a utility, but `wchat export <mp_id>` should no longer use it for article export because preserving stored HTML is the desired reading format.

## Goals / Non-Goals

**Goals:**
- Export each article as a complete standalone `.html` document.
- Preserve the article's stored HTML body instead of converting it to Markdown.
- Provide a readable local HTML wrapper with stable metadata and lightweight CSS.
- Keep the existing command shape, export directory, ordering, incrementality, and `--force` behavior.
- Keep implementation dependency-free using Python standard library escaping plus existing project code.

**Non-Goals:**
- No Markdown, JSONL, PDF, EPUB, or multi-format output.
- No image downloading or asset mirroring in this change.
- No generated `index.html` in this change unless explicitly added later.
- No database migration or article content mutation.
- No change to fetch, RSS attribution, summaries, or stored HTML sanitization.

## Decisions

1. Replace Markdown builder with an HTML document builder.

   Introduce or rename a builder such as `build_article_html(article_obj: Article) -> str`. The builder should produce a full document:

   ```html
   <!doctype html>
   <html lang="zh-CN">
   <head>
     <meta charset="utf-8">
     <meta name="viewport" content="width=device-width, initial-scale=1">
     <title>...</title>
     <style>...</style>
   </head>
   <body>
     <main class="article">
       <header class="article-header">...</header>
       <article class="article-content">...</article>
     </main>
   </body>
   </html>
   ```

   Rationale: exporting a fragment-only HTML file is less useful in browsers and makes metadata styling inconsistent. A full document is still simple and dependency-free.

2. Escape metadata, preserve body HTML.

   Metadata fields controlled by the database, such as title, summary, original URL, cover URL, and formatted publish time, should be escaped with `html.escape()` before insertion. `Article.content` should be inserted as the article body without Markdown conversion so that existing WeChat/RSS HTML layout is preserved.

   Rationale: metadata belongs to the template and should not break the wrapper. The stored body is already the content being archived; converting or escaping the whole body would defeat the purpose of HTML export.

3. Keep output directory and incrementality unchanged.

   Continue writing under `output/export_articles/<mp_id>/`. In normal mode, skip a generated `.html` file if it already exists. With `--force`, remove and rebuild the export directory as today.

   Existing `.md` files from previous exports are not deleted in normal incremental mode. With `--force`, they are removed because the directory is rebuilt.

   Rationale: users keep the same command and storage location. The only intentional output change is file format.

4. Change filename extension and collision logic to HTML.

   `build_export_filename()` should generate `.html` filenames and check collisions against `.html` files. Date prefix and sanitized title logic remain unchanged.

   Rationale: this is the smallest behavioral change that matches the new output format while preserving stable sorting and human-readable filenames.

5. Use lightweight embedded CSS.

   The template should include minimal CSS:
   - centered readable content width
   - system font stack
   - responsive images with `max-width: 100%; height: auto`
   - subdued metadata block
   - summary callout
   - reasonable line height and background

   Rationale: local HTML files should be readable immediately without external assets or build tooling. Embedded CSS avoids extra files and broken relative paths.

## Risks / Trade-offs

- Stored article HTML may include inline styles from WeChat that override wrapper CSS → Keep wrapper CSS conservative and avoid fighting article body styles.
- Remote images still depend on source availability → This change intentionally does not mirror assets; image localization can be a later proposal.
- Existing users expecting `.md` files will see `.html` outputs after the change → Document as a user-visible behavior change and preserve command name.
- Unescaped metadata could break HTML if titles contain special characters → Escape all metadata inserted by the template.
- Tests tied to `build_article_markdown()` will need updates → Replace export-flow tests with `build_article_html()` expectations while keeping standalone `html_to_markdown()` tests intact.

## Migration Plan

No database migration is required. Existing exported Markdown files remain on disk unless the user runs `wchat export <mp_id> --force`, which already clears the export directory. After implementation, users can regenerate a clean HTML-only export by running the command with `--force`.

## Open Questions

- None for this scope. Index pages, local image mirroring, and optional archive bundles are intentionally excluded.
