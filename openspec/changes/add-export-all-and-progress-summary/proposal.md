## Why

After article export switches to HTML, users still need a practical way to export the whole local article archive without manually running one command per public account. The current export output also only prints a final two-line summary, which is too sparse for batch work and makes it hard to understand mode, target directory, skipped articles, and failures.

## What Changes

- Add `wchat export --all` to export articles for all subscriptions/public accounts.
- Keep `wchat export <mp_id>` for single-public-account export.
- Preserve incremental behavior by default for both single and all-account export.
- Preserve `--force` for both modes:
  - single mode rebuilds that public account's export directory
  - `--all --force` rebuilds each exported public account's directory
- Improve terminal output for export commands:
  - show export scope: single account or all accounts
  - show export mode: incremental or force rebuild
  - show output format: HTML
  - show output directory per public account
  - show per-account counts: exported, skipped, failed, total
  - show aggregate totals for `--all`
  - show clear messages for no articles, no subscriptions, and no new exported articles
- Track per-article write failures so one bad article does not hide the overall result.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `html-to-markdown`: Extend the HTML article export flow with all-subscription export and clearer terminal progress/summary reporting.

## Impact

- Affected code:
  - `src/cli/article.py`
  - tests around `wchat export` command behavior and terminal output
- Depends on the HTML export behavior from `export-articles-as-html`.
- No database schema changes.
- No new runtime dependency.
- No change to article fetching, RSS attribution, AI summaries, or stored article content.
