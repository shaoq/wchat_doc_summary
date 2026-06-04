## Why

`wchat export --all` currently exports every active public account, but users need a way to exclude noisy or low-value accounts from default batch export while still allowing explicit one-off export. Without a visible per-account flag, an active subscription that is skipped by batch export would be hard to understand from `wchat ls`.

## What Changes

- Add a per-public-account batch export preference, defaulting to enabled for new and existing subscriptions.
- Make `wchat export --all` export only active subscriptions whose batch export preference is enabled.
- Keep `wchat export <MP_ID>` explicit export behavior independent of the batch export preference.
- Add a command under the export domain to update the preference:
  - `wchat export set-export <MP_ID> true`
  - `wchat export set-export <MP_ID> false`
- Show the batch export preference in `wchat ls`.
- Show the batch export preference in `wchat info <MP_ID>` for detail visibility.
- Report clearly when `wchat export --all` has active subscriptions but none are enabled for batch export.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `subscription`: Store, display, and update each subscription's default batch export preference.
- `html-to-markdown`: Update article HTML export behavior so `wchat export --all` respects the subscription-level batch export preference while explicit single-account export remains allowed.

## Impact

- Database: `feeds` table gains one boolean-like column with default enabled for backward compatibility.
- Model: `Feed` gains one batch export preference field.
- CLI:
  - `wchat export` needs to support a `set-export` subcommand while preserving existing `wchat export <MP_ID>`, `wchat export --all`, and `wchat export --all --force` usage.
  - `wchat ls` and `wchat info` output gain a visible batch export field.
- Tests:
  - export-all filtering behavior
  - explicit export bypass behavior
  - preference setting command
  - list/info display
  - database default and compatibility migration
- No new runtime dependency.
- No change to article fetching, RSS source ingestion, AI processing, or exported HTML file format.
