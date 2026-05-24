## Context

`wchat export <mp_id>` currently exports a single public account. After `export-articles-as-html`, the command writes HTML files but still keeps the original single-account command shape and sparse terminal summary. Users who maintain many subscriptions need a batch export path, and both single and batch modes need clearer progress and final reporting.

This change should be implemented after or on top of `export-articles-as-html`. It assumes the exported article format is HTML and the per-article builder writes `.html` files.

## Goals / Non-Goals

**Goals:**
- Add `wchat export --all` for exporting every subscription/public account.
- Preserve `wchat export <mp_id>` for targeted export.
- Keep default export incremental in both modes.
- Preserve `--force` for rebuilding export directories.
- Emit clear terminal logs for scope, mode, format, output directory, per-account progress, and totals.
- Continue processing other public accounts and articles when one article write fails.

**Non-Goals:**
- No new export formats.
- No index page generation.
- No image mirroring.
- No scheduling/background job support.
- No database schema changes.
- No archive packaging or compression.

## Decisions

1. Make `MP_ID` optional and add `--all`.

   CLI shape:

   ```bash
   wchat export <mp_id>
   wchat export <mp_id> --force
   wchat export --all
   wchat export --all --force
   ```

   Validation rules:
   - If neither `mp_id` nor `--all` is provided, show a clear usage error.
   - If both `mp_id` and `--all` are provided, show a clear usage error.

   Rationale: this keeps the existing command name and avoids introducing a second batch command.

2. Factor export work into reusable units.

   Introduce internal helpers around the existing command:
   - `ExportSummary` or equivalent dataclass with `exported`, `skipped`, `failed`, `total`, `output_dir`, and feed identity fields.
   - `export_feed_articles(feed, articles, force) -> ExportSummary` or similar.
   - a query helper for single feed and a query helper for all feeds.

   Rationale: single and all-account modes need the same export semantics and summary fields. A shared helper reduces behavior drift.

3. Select all subscriptions deterministically.

   `--all` should export feeds ordered by a stable field such as `Feed.name` then `Feed.mp_id`, or by `Feed.id` if the existing UX expects creation order. Inactive feeds should be included or excluded deliberately. Recommended default: export all active feeds (`Feed.status == 1`) because the command is for current subscriptions.

   Rationale: deterministic order makes terminal output and reruns easier to compare.

4. Make terminal output explicit and compact.

   Single-account mode should print:
   - account name and mp_id
   - mode: incremental or force rebuild
   - format: HTML
   - output directory
   - final counts

   `--all` mode should print:
   - batch scope and account count
   - mode and format
   - per-account progress line with `[idx/total]`
   - per-account counts
   - aggregate totals

   Example:

   ```text
   批量导出: 42 个公众号
   模式: 增量
   格式: HTML

   [1/42] 证券时报 (biz:xxx)
     输出目录: output/export_articles/biz:xxx
     新导出: 12，已存在跳过: 238，失败: 0，总计: 250

   总计
     公众号: 42
     新导出: 120
     已存在跳过: 3180
     失败: 0
     文章总数: 3300
   ```

   Rationale: users should be able to tell what happened without inspecting the output directory.

5. Count per-article failures, do not abort the whole batch on a single write failure.

   If writing one article fails, log a concise warning including article id/title and continue with the next article. The summary should increment `failed`. If a whole feed cannot be queried or its directory cannot be prepared, record that feed as failed and continue with other feeds in `--all` mode.

   Rationale: archive export is batch-oriented; one malformed title, permission issue, or unexpected file error should not hide progress for other accounts.

6. Keep `--force` scoped per account.

   Single mode `--force` clears only that account's export directory. `--all --force` clears each account directory immediately before exporting that account. It should not delete the entire `output/export_articles` root in one step.

   Rationale: per-account deletion is easier to reason about and reduces blast radius if the root contains unrelated files.

## Risks / Trade-offs

- `--all --force` can delete many per-account export directories → Logs must clearly show force rebuild mode before work starts.
- Continuing after article failures can hide problems if the final summary is overlooked → Non-zero failure counts should be highlighted in red/yellow terminal output.
- Selecting only active feeds may surprise users expecting inactive historical feeds → Document the active-feed behavior in help text; a future proposal can add inactive inclusion if needed.
- More verbose logs can become noisy for many accounts → Use per-account summaries, not one line per successful article.

## Migration Plan

No data migration is required. Existing single-account usage continues to work. Users can run `wchat export --all` for incremental batch export, or `wchat export --all --force` for a clean rebuild of every active account's HTML export directory.

## Open Questions

- Should inactive feeds be included in `--all`? This design recommends active-only for the first version.
