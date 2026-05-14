## ADDED Requirements

### Requirement: README documents RSS SaaS as the primary workflow
The README SHALL describe the RSS SaaS workflow as the recommended article-fetching path while retaining WeRead and Wechat2RSS as compatibility paths.

#### Scenario: User reads setup overview
- **WHEN** a user reads the README setup and common workflow sections
- **THEN** the README SHALL explain that RSS SaaS sync does not require `wchat login`
- **AND** it SHALL explain that WeRead-backed workflows still require login

### Requirement: README documents RSS configuration boundaries
The README SHALL explain which RSS settings belong in `.env` and which RSS source data is managed locally.

#### Scenario: User configures WeChat RSS SaaS
- **WHEN** a user follows README configuration instructions
- **THEN** the README SHALL show the global WeChat RSS API key in `.env`
- **AND** it SHALL state that aggregate/category RSS URLs are configured as local RSS sources rather than `.env` entries

### Requirement: README documents aggregate and category RSS source modes
The README SHALL document both single aggregate RSS source mode and multiple category RSS source mode.

#### Scenario: User has one aggregate RSS feed
- **WHEN** a user has one RSS feed containing all public accounts
- **THEN** the README SHALL show how to configure it as a single source such as `全部`

#### Scenario: User has multiple category RSS feeds
- **WHEN** a user has separate RSS feeds by category
- **THEN** the README SHALL show how to configure multiple named sources
- **AND** it SHALL explain how `wchat ls` displays source/category membership

### Requirement: README documents RSS auto-discovered subscriptions
The README SHALL explain that RSS sync can create local public-account subscriptions automatically when new accounts appear in RSS feeds.

#### Scenario: User sees unexpected subscription in list output
- **WHEN** RSS sync has auto-discovered a new public account
- **THEN** the README SHALL explain why it appears in `wchat ls`
- **AND** it SHALL document the settings controlling auto-subscribe behavior and default status

### Requirement: README FAQ covers RSS operational behavior
The README FAQ SHALL cover common RSS SaaS operational questions.

#### Scenario: User reads FAQ after RSS setup
- **WHEN** a user reads the FAQ
- **THEN** it SHALL cover RSS login requirements, API key placement, source URL management, auto-subscribe behavior, deduplication across sources, and source health basics
