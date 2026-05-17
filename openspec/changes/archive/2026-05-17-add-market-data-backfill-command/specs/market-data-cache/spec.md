## ADDED Requirements

### Requirement: Cache writes SHALL prevent historical snapshot contamination
The market-data cache layer SHALL reject or avoid writes that would store realtime snapshot data under a historical trade date.

#### Scenario: Unsupported historical category is not written
- **WHEN** a market-data category is marked as realtime-only
- **AND** a caller attempts to backfill that category for a historical trade date
- **THEN** the cache write workflow SHALL skip that category
- **AND** no row for that category SHALL be created from realtime snapshot data

#### Scenario: Historical-safe category may write historical rows
- **WHEN** a market-data category is marked as historical-safe
- **AND** validated data is returned for the requested trade date
- **THEN** the cache write workflow SHALL persist that data using the requested trade date

### Requirement: Cache SHALL preserve valid rows across partial backfill failures
The market-data cache SHALL not replace existing valid rows with empty, failed, or unsupported backfill results.

#### Scenario: Failed category preserves existing rows
- **WHEN** valid cache rows already exist for a trade date and category
- **AND** a backfill attempt for that category fails
- **THEN** the existing cache rows SHALL remain unchanged

#### Scenario: Empty category preserves existing rows
- **WHEN** valid cache rows already exist for a trade date and category
- **AND** a backfill attempt returns no historical records for that category
- **THEN** the existing cache rows SHALL remain unchanged
