## Context

`wchat export --all` currently selects every active `Feed` and exports each feed's articles to `output/export_articles/<mp_id>/`. Users want a per-public-account switch that controls only default batch export participation. Explicit export by `wchat export <MP_ID>` must remain available even when that switch is disabled.

The existing subscription model already separates `status` from other feed metadata such as `weight`. `status` controls active/inactive subscription semantics across fetching and listing, while `weight` controls fetch priority. The new export preference should be independent of both.

## Goals / Non-Goals

**Goals:**
- Add a persisted per-feed batch export preference with default enabled.
- Preserve backward compatibility for existing databases and existing export commands.
- Let users update the preference through an export-domain CLI command.
- Make the preference visible in `wchat ls` and `wchat info`.
- Make `wchat export --all` honor the preference while preserving explicit `wchat export <MP_ID>`.

**Non-Goals:**
- Do not change fetch ordering or fetch inclusion.
- Do not change subscription active/inactive semantics.
- Do not introduce export profiles, tags, or multi-select filters.
- Do not change exported HTML content, filename rules, output directory layout, or force rebuild semantics.
- Do not add a global configuration default for newly created feeds in this change.

## Decisions

### D1: Add an independent Feed field for batch export inclusion

Use a boolean-like field on `Feed`, for example `include_in_export_all`, stored in SQLite as an integer with default `1`.

Alternatives considered:
- Reuse `status`: rejected because inactive subscriptions affect fetch/list semantics and would make "skip default export" too broad.
- Reuse `weight`: rejected because weight is already fetch-priority metadata and does not express export inclusion.
- Store in `provider_meta`: rejected because this is first-class user preference and needs query/filter/display support.

Rationale: a dedicated field keeps behavior explicit, queryable, and compatible with current subscription semantics.

### D2: Default existing and new subscriptions to included

New `Feed` records should default to `include_in_export_all = 1`. Existing SQLite databases should be upgraded through the existing compatibility-column mechanism with the same default.

Rationale: current `export --all` users expect active subscriptions to be exported. Defaulting to included avoids surprising data omissions after upgrade.

### D3: Filter only the `--all` feed selection

`wchat export --all` should select feeds where `Feed.status == 1` and `Feed.include_in_export_all == 1`, with the existing deterministic order retained. `wchat export <MP_ID>` should continue to look up the feed by `mp_id` and export it regardless of the preference.

Rationale: the preference means "included in default batch export", not "export locked".

### D4: Put the setter under the export command domain while preserving legacy parsing

Expose the setter as:

```bash
wchat export set-export <MP_ID> true
wchat export set-export <MP_ID> false
```

To support this while preserving existing usage, keep `export` as the top-level command surface and dispatch the `set-export` verb under that command. The implementation may use a Click group if it can preserve all existing argument forms, or an equivalent command wrapper that parses `set-export` before normal export validation.

Existing usage to preserve:

```bash
wchat export <MP_ID>
wchat export <MP_ID> --force
wchat export --all
wchat export --all --force
```

Alternatives considered:
- Add a top-level `wchat set-export` command: simpler implementation, but less discoverable because the setting only affects export behavior.
- Add the setting under subscription commands: semantically plausible, but the user-facing effect is specifically `export --all`.
- Convert to a plain Click group with optional `MP_ID`: rejected during implementation because Click subcommand parsing conflicts with existing `wchat export <MP_ID> --force` and `wchat export set-export <MP_ID> false` forms unless extra custom parsing is added.

Rationale: keeping the setter under `export` makes command discovery and help text align with the affected behavior.

### D5: Display the preference in list and detail views

`wchat ls` should add a compact "批量导出" column with values such as "是"/"否". `wchat info <MP_ID>` should show the same preference in the detail panel.

Rationale: users need to understand why an active subscription is skipped by `export --all` without inspecting the database.

## Risks / Trade-offs

- [CLI compatibility] Changing `export` from a command to a group can break positional parsing if not handled carefully. Mitigation: use Click's invoke-without-command pattern or equivalent tests covering every existing export invocation.
- [Output width] Adding a `wchat ls` column can make the table wider. Mitigation: use a short column label and short values.
- [Ambiguous no-work state] `export --all` can find active subscriptions but none enabled for batch export. Mitigation: print a distinct message from "没有活跃的订阅".
- [SQLite boolean behavior] SQLite has no native boolean type. Mitigation: use integer 1/0 consistently and expose Python-side values as bool-like.

## Migration Plan

1. Add the model field with default enabled.
2. Extend the database compatibility path to add the column to existing `feeds` tables with default `1`.
3. Update export selection to filter on the new field for `--all`.
4. Add the setter command and register it while preserving existing command behavior.
5. Update list/detail output and tests.

Rollback is straightforward: stop filtering on the field and ignore the column. The extra SQLite column can remain without affecting older behavior.

## Open Questions

- Exact field name can be finalized during implementation. Recommended: `include_in_export_all` because it directly describes the command it affects.
- Exact display wording can be finalized with implementation. Recommended column label: `批量导出`.
