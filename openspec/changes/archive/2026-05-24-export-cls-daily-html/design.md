## Context

CLS data is stored locally in two tables:
- `cls_telegraphs`: important telegraph items with title, content, timestamp, level, and category.
- `cls_watch_data`: watch items with title, content, timestamp, type, stocks JSON, sectors JSON, and category.

The existing `wchat cls` command group can fetch and list these records, but cannot export them. The export should be local-only: users explicitly fetch data first, then export whatever is present in the database.

Daily files are the right unit because CLS data is a time stream and users review it by trading/calendar day. File-level incrementality is enough: if a daily output file exists, skip it unless `--force` is used.

## Goals / Non-Goals

**Goals:**
- Add `wchat cls export` for daily HTML export.
- Support a single date, defaulting to the current local date.
- Support `--all` to export every date present in local CLS data.
- Support `--type all|telegraphs|watch`.
- Export one HTML file per date/type target.
- Skip existing output files by default and overwrite only with `--force`.
- Render readable HTML with overview stats, telegraph section, and watch section.
- Escape all stored text fields before writing HTML.

**Non-Goals:**
- Do not auto-fetch missing CLS data.
- Do not support Markdown, JSON, CSV, PDF, or EPUB output.
- Do not support `--hours` or arbitrary cross-day windows in the first version.
- Do not create a global index page in the first version.
- Do not modify stored CLS rows.

## Decisions

1. CLI shape and validation.

   Supported commands:

   ```bash
   wchat cls export
   wchat cls export --date 2026-05-24
   wchat cls export --all
   wchat cls export --all --force
   wchat cls export --date 2026-05-24 --force
   wchat cls export --type telegraphs
   wchat cls export --type watch
   wchat cls export --type all
   wchat cls export --date 2026-05-24 --output output/custom.html
   ```

   Validation:
   - `--date` and `--all` are mutually exclusive.
   - `--output` is only valid for single-date export, not `--all`.
   - `--type` defaults to `all`.

   Rationale: the command stays compact while avoiding ambiguous output paths.

2. Output paths.

   Default output directory:

   ```text
   output/cls_exports/
   ```

   File naming:
   - `YYYY-MM-DD.html` for `--type all`
   - `YYYY-MM-DD_telegraphs.html` for `--type telegraphs`
   - `YYYY-MM-DD_watch.html` for `--type watch`

   Rationale: date-first filenames sort naturally and keep all daily exports in one directory.

3. Date windows.

   A daily export covers local calendar time:

   ```text
   YYYY-MM-DD 00:00:00 <= ctime <= YYYY-MM-DD 23:59:59
   ```

   `--all` discovers dates from the union of local dates in `cls_telegraphs.ctime` and `cls_watch_data.ctime`, filtered by `--type`.

   Rationale: this avoids confusing cross-day files and makes incrementality file-based.

4. Data querying.

   Reuse existing services where practical:
   - `CLSTelegraphService.list_telegraphs(start_time, end_time, limit=...)`
   - `CLSWatchService.list_watch_data(start_time, end_time, limit=...)`

   Use a sufficiently high limit or add service support for unbounded daily export if needed. Items render newest-first inside each section.

   Rationale: service reuse keeps query behavior consistent with existing list commands.

5. HTML rendering.

   Add helper functions such as:
   - `build_cls_export_html(date, export_type, telegraphs, watch_items, generated_at)`
   - `render_telegraphs_section(items)`
   - `render_watch_section(items)`
   - `build_cls_export_path(date, export_type)`

   HTML structure:
   - document head with UTF-8 charset and viewport
   - embedded CSS
   - header with date, type, generated time, and counts
   - overview cards
   - telegraph section when included
   - watch section when included

   Rendering details:
   - Telegraph level badges: A red, B amber, C muted.
   - Watch data type badges.
   - Stocks and sectors as compact tags.
   - Text content escapes HTML and preserves line breaks as `<br>`.
   - JSON parse failures for stocks/sectors degrade to empty lists.

   Rationale: CLS content is stored as data/text, not trusted article HTML, so it must be escaped.

6. Incrementality and force behavior.

   Single-date export:
   - if target file exists and `--force` is not set, skip and print a clear message
   - if `--force` is set, overwrite

   `--all`:
   - for each date, skip existing target file unless `--force`
   - continue exporting other dates after a skipped file
   - final summary includes exported and skipped date counts

   Rationale: daily files become the export state. No extra manifest or database state is needed.

7. Terminal output.

   Single-date export should show:
   - date
   - type
   - mode: incremental or force
   - output path
   - telegraph/watch counts
   - exported/skipped status

   `--all` should show:
   - number of dates
   - type
   - mode
   - output directory
   - per-date progress `[current/total]`
   - aggregate exported/skipped counts and item counts

## Risks / Trade-offs

- Large `--all` exports may create many files → Daily files are intentional and safer than a single giant file.
- Daily local-date grouping depends on system timezone → This matches existing CLI behavior and user locale.
- Existing service limits could truncate data → Implementation should explicitly choose a high safe limit or add an export-specific query path.
- `--output` with `--all` is ambiguous → Reject it instead of inventing a directory-vs-file interpretation.
- HTML files do not auto-update after new CLS fetches → This is the file-level incremental contract; users can use `--force` to rebuild a date.

## Migration Plan

No migration is required. The command creates new files under `output/cls_exports/`. Existing CLS fetch/list behavior is unchanged.

## Open Questions

- None for the first version. A future change can add an index page for `output/cls_exports/`.
