## ADDED Requirements

### Requirement: Fetch pipeline uses the configured article list provider
The article fetch pipeline SHALL obtain article lists through the configured provider abstraction rather than assuming WeRead-specific list APIs.

#### Scenario: Fetch feed with non-WeRead provider
- **WHEN** the fetch pipeline is configured to use a non-WeRead provider
- **THEN** the system fetches article list items from that provider
- **AND** it continues importing articles through the same downstream parsing and storage flow

### Requirement: Article content fetch supports full article URLs
The system SHALL support fetching article content by full article URL, not only by a WeChat `/s/<article_id>` short identifier.

#### Scenario: Provider returns full article URL
- **WHEN** a provider article item contains a complete WeChat article URL
- **THEN** the content fetch stage uses that URL directly to retrieve the article HTML
- **AND** it does not require the provider to first convert the URL into a short article ID

### Requirement: Imported articles are deduplicated across providers
The system SHALL deduplicate imported articles across provider sources using stable article identity information, including original URL and provider metadata when available.

#### Scenario: Same article appears from two providers
- **WHEN** two providers return the same WeChat article through different upstream identifiers
- **THEN** the system avoids importing duplicate article records
- **AND** the resulting stored article remains associated with its source metadata
