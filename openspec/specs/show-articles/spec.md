# show-articles Specification

## Purpose
TBD - created by archiving change add-show-articles-command. Update Purpose after archive.
## Requirements
### Requirement: Show command displays article list
The system SHALL provide a `show` command that displays articles for a specified subscription.

#### Scenario: Display articles with default pagination
- **WHEN** user runs `wchat show <mp_id>` without options
- **THEN** system displays up to 20 articles sorted by publish time (newest first)
- **AND** shows article ID, title, original URL, and publish time in table format

#### Scenario: Display articles with custom limit
- **WHEN** user runs `wchat show <mp_id> --limit 10`
- **THEN** system displays up to 10 articles

#### Scenario: Display articles with offset
- **WHEN** user runs `wchat show <mp_id> --offset 20`
- **THEN** system skips first 20 articles and displays the next page

#### Scenario: Display all articles
- **WHEN** user runs `wchat show <mp_id> --all`
- **THEN** system displays all articles without pagination limit

### Requirement: Show command validates subscription existence
The system SHALL validate that the subscription exists before querying articles.

#### Scenario: Non-existent subscription
- **WHEN** user runs `wchat show <non_existent_mp_id>`
- **THEN** system displays error message "订阅不存在: <mp_id>"

### Requirement: Show command handles empty article list
The system SHALL handle cases where no articles have been fetched.

#### Scenario: No articles fetched
- **WHEN** user runs `wchat show <mp_id>` for a subscription with no articles
- **THEN** system displays message "该公众号暂无已抓取的文章"

### Requirement: Show command handles missing data gracefully
The system SHALL display fallback text for missing article fields.

#### Scenario: Missing original URL
- **WHEN** article has no original_url
- **THEN** system displays "无" in the URL column

#### Scenario: Missing publish time
- **WHEN** article has no publish_time
- **THEN** system displays "未知" in the publish time column

### Requirement: Show command provides pagination hints
The system SHALL inform users when more articles are available.

#### Scenario: More articles available
- **WHEN** displayed articles count equals limit AND total count exceeds limit
- **THEN** system shows hint with current range and next offset command

