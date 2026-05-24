## ADDED Requirements

### Requirement: CLS data can be exported as daily HTML
The system SHALL provide `wchat cls export` to export local CLS data into daily HTML files.

#### Scenario: Export current local date by default
- **WHEN** the user runs `wchat cls export`
- **THEN** the system SHALL export CLS data for the current local date
- **AND** it SHALL use export type `all`
- **AND** it SHALL write an HTML file under `output/cls_exports/`

#### Scenario: Export a specified date
- **WHEN** the user runs `wchat cls export --date 2026-05-24`
- **THEN** the system SHALL export CLS data for local calendar date `2026-05-24`
- **AND** it SHALL use the time window `2026-05-24 00:00:00` through `2026-05-24 23:59:59`

#### Scenario: Export all local dates
- **WHEN** the user runs `wchat cls export --all`
- **THEN** the system SHALL discover all local dates that have matching CLS data
- **AND** it SHALL export one HTML file per discovered date
- **AND** it SHALL process dates deterministically

#### Scenario: Export reads local data only
- **WHEN** `wchat cls export` runs
- **THEN** the system SHALL read from local CLS database tables
- **AND** it SHALL NOT fetch remote CLS data automatically

### Requirement: CLS export supports data type selection
The CLS export command SHALL support exporting telegraphs, watch data, or both.

#### Scenario: Export both CLS data types
- **WHEN** the user runs `wchat cls export --type all`
- **THEN** the output HTML SHALL include telegraph data when present
- **AND** it SHALL include watch data when present

#### Scenario: Export telegraphs only
- **WHEN** the user runs `wchat cls export --type telegraphs`
- **THEN** the output HTML SHALL include only CLS telegraph data
- **AND** it SHALL NOT include a watch data section

#### Scenario: Export watch data only
- **WHEN** the user runs `wchat cls export --type watch`
- **THEN** the output HTML SHALL include only CLS watch data
- **AND** it SHALL NOT include a telegraph section

### Requirement: CLS export writes predictable daily file paths
The CLS export command SHALL use deterministic daily HTML file paths unless the user provides a single-date custom output path.

#### Scenario: Default all-type output path
- **WHEN** the user exports date `2026-05-24` with type `all`
- **THEN** the default output path SHALL be `output/cls_exports/2026-05-24.html`

#### Scenario: Telegraph-only output path
- **WHEN** the user exports date `2026-05-24` with type `telegraphs`
- **THEN** the default output path SHALL be `output/cls_exports/2026-05-24_telegraphs.html`

#### Scenario: Watch-only output path
- **WHEN** the user exports date `2026-05-24` with type `watch`
- **THEN** the default output path SHALL be `output/cls_exports/2026-05-24_watch.html`

#### Scenario: Custom output path for single date
- **WHEN** the user runs `wchat cls export --date 2026-05-24 --output custom.html`
- **THEN** the system SHALL write the single-date export to `custom.html`

#### Scenario: Custom output path rejected with all dates
- **WHEN** the user runs `wchat cls export --all --output custom.html`
- **THEN** the command SHALL fail with a clear usage message
- **AND** it SHALL NOT export files

### Requirement: CLS export is file-incremental by default
The CLS export command SHALL skip existing daily HTML files by default and overwrite only when `--force` is supplied.

#### Scenario: Existing daily file is skipped
- **WHEN** the target HTML file already exists
- **AND** the user did not pass `--force`
- **THEN** the command SHALL skip writing that file
- **AND** it SHALL report the skip in terminal output

#### Scenario: Force overwrites existing daily file
- **WHEN** the target HTML file already exists
- **AND** the user passes `--force`
- **THEN** the command SHALL overwrite the target file
- **AND** it SHALL report the export as rebuilt

#### Scenario: All-date export skips existing files independently
- **WHEN** the user runs `wchat cls export --all`
- **AND** some discovered daily output files already exist
- **THEN** the command SHALL skip existing files
- **AND** it SHALL continue exporting dates whose files do not exist

### Requirement: CLS daily HTML is readable and safe
The generated CLS HTML SHALL be a complete browser-readable document and SHALL escape stored CLS text fields.

#### Scenario: HTML document structure
- **WHEN** a CLS daily export file is generated
- **THEN** it SHALL contain `<!doctype html>`, `<html>`, `<head>`, and `<body>`
- **AND** it SHALL include UTF-8 charset metadata
- **AND** it SHALL include a responsive viewport meta tag

#### Scenario: Daily overview is rendered
- **WHEN** a CLS daily export file is generated
- **THEN** it SHALL display the export date
- **AND** it SHALL display generated time
- **AND** it SHALL display telegraph and watch item counts for included types

#### Scenario: Telegraph section is rendered
- **WHEN** telegraph data is included
- **THEN** each telegraph item SHALL show publish time, level, title, and content when available
- **AND** level badges SHALL visually distinguish A, B, and C levels

#### Scenario: Watch section is rendered
- **WHEN** watch data is included
- **THEN** each watch item SHALL show publish time, data type, title, content when available, stocks, and sectors
- **AND** stocks and sectors SHALL be rendered as readable tags when present

#### Scenario: Stored text is escaped
- **WHEN** CLS title, content, stock, or sector values contain HTML-like text
- **THEN** the generated HTML SHALL escape those values
- **AND** it SHALL NOT execute stored text as markup or script

### Requirement: CLS export terminal output is clear
The CLS export command SHALL print clear terminal output for scope, mode, output path, and result counts.

#### Scenario: Single-date export output
- **WHEN** a single-date export runs
- **THEN** terminal output SHALL show date, type, mode, and output path
- **AND** completion output SHALL show telegraph count and watch count for included types

#### Scenario: All-date export output
- **WHEN** `wchat cls export --all` runs
- **THEN** terminal output SHALL show discovered date count, type, mode, and output directory
- **AND** it SHALL show per-date progress
- **AND** final output SHALL show exported file count, skipped file count, and aggregate item counts

#### Scenario: No matching local data
- **WHEN** the selected date or all-date scope has no matching local CLS data
- **THEN** the command SHALL print a clear no-data message
- **AND** it SHALL NOT generate an empty HTML file
