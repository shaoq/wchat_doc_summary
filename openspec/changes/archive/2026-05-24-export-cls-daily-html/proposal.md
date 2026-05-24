## Why

The project can fetch and list local CLS telegraph/watch data, but it lacks a browser-readable export for daily review. CLS data is inherently time-series and review-oriented, so daily HTML files provide a simple archive format that supports both single-day review and incremental batch export without maintaining a separate export state table.

## What Changes

- Add `wchat cls export` to export local CLS data as HTML.
- Default export scope is the current local date.
- Add `--date YYYY-MM-DD` for exporting one specific day.
- Add `--all` for exporting every local date that has CLS telegraph or watch data.
- Add `--type all|telegraphs|watch`, defaulting to `all`.
- Add `--output PATH` for single-date custom output.
- Add `--force` to overwrite existing output files.
- Use file-level incremental behavior by default: if the target daily HTML already exists, skip it unless `--force` is supplied.
- Write daily files under `output/cls_exports/`:
  - `YYYY-MM-DD.html` for `--type all`
  - `YYYY-MM-DD_telegraphs.html` for telegraphs-only
  - `YYYY-MM-DD_watch.html` for watch-only
- Render both telegraphs and watch data in one daily HTML document for the default `all` type.
- Do not auto-fetch missing CLS data during export; export reads local database only.
- Do not support `--hours` in this first version because daily files should contain one calendar day.

## Capabilities

### New Capabilities
- `cls-daily-html-export`: Covers daily HTML export of local CLS telegraph/watch data, including single-day export, all-date export, file-level incrementality, and terminal summaries.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/cli/cls_data.py`
  - likely a new helper module or service for CLS export rendering
  - tests for CLS CLI command behavior and generated HTML
- Reads existing tables:
  - `cls_telegraphs`
  - `cls_watch_data`
- No database schema changes.
- No new runtime dependency.
- No change to CLS fetch behavior, market summary generation, or article export.
