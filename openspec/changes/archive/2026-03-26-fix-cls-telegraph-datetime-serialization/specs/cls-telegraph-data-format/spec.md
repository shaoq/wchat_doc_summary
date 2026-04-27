# CLS Telegraph Data Format Specification

This specification defines the data format requirements for CLS telegraph data returned by the API client.

---

## ADDED Requirements

### Requirement: Telegraph data shall be JSON serializable

The system SHALL ensure that all fields in CLS telegraph data returned by `parse_telegraph` method are directly JSON serializable without custom encoders.

#### Scenario: Serialize telegraph data to JSON
- **WHEN** calling `json.dumps()` on telegraph data returned by `parse_telegraph`
- **THEN** serialization succeeds without `TypeError`
- **AND** all fields are properly encoded in JSON format

---

### Requirement: publish_time shall be ISO 8601 string

The system SHALL return `publish_time` as an ISO 8601 formatted string, not as a `datetime` object.

#### Scenario: Parse telegraph returns ISO string
- **WHEN** calling `parse_telegraph` method with a telegraph item
- **THEN** `publish_time` field is a string in ISO 8601 format (e.g., "2026-03-26T14:30:00")
- **AND** `publish_time` is not a `datetime` object

#### Scenario: Preserve time precision
- **WHEN** converting timestamp to ISO string
- **THEN** no time information is lost during conversion
- **AND** the ISO string accurately represents the original timestamp

#### Scenario: Handle None timestamp
- **WHEN** telegraph item has no `ctime` (ctime = 0 or None)
- **THEN** `publish_time` is None
- **AND** no exception is raised

---

### Requirement: Telegraph data format consistency

The system SHALL maintain consistent data format across all data sources in the project.

#### Scenario: Match fetch_time format
- **WHEN** formatting `publish_time` in telegraph data
- **THEN** format matches `fetch_time` format in `finance.py` (both use `.isoformat()`)
- **AND** both use ISO 8601 standard

#### Scenario: Compatibility with f-string formatting
- **WHEN** using `publish_time` in f-string (e.g., in AI prompt)
- **THEN** string displays correctly without explicit conversion
- **AND** format is human-readable

---

### Requirement: Telegraph data validation

The system SHALL validate telegraph data structure before returning.

#### Scenario: Validate required fields
- **WHEN** `parse_telegraph` processes a telegraph item
- **THEN** returned data includes all required fields: `title`, `content`, `publish_time`, `level`, `ctime`
- **AND** all fields have correct data types

#### Scenario: Handle missing optional fields
- **WHEN** telegraph item is missing optional fields
- **THEN** system uses appropriate default values
- **AND** no KeyError or AttributeError is raised
