## ADDED Requirements

### Requirement: Extract stocks from article content

The system SHALL extract A-share stock information (stock name and code) from article content using LLM.

#### Scenario: Article contains stocks
- **WHEN** article content mentions A-share stocks
- **THEN** system returns stock list in format "股票名称（股票代码）"

#### Scenario: Article contains no stocks
- **WHEN** article content mentions no A-share stocks
- **THEN** system returns empty result

#### Scenario: Article contains non-A-share stocks
- **WHEN** article mentions only Hong Kong or US stocks
- **THEN** system returns empty result (only A-share stocks are extracted)

### Requirement: Record processing status

The system SHALL record the processing status and result in `ArticleProcessing` table for each article.

#### Scenario: Successful extraction
- **WHEN** stock extraction completes successfully
- **THEN** system creates ArticleProcessing record with status "success" and result in JSON format

#### Scenario: Failed extraction
- **WHEN** stock extraction fails due to LLM error
- **THEN** system creates ArticleProcessing record with status "failed"

### Requirement: Skip already processed articles

The system SHALL skip articles that have already been processed for stock extraction by default.

#### Scenario: Article already processed
- **WHEN** article has existing ArticleProcessing record with task_type "extract_stocks"
- **THEN** system skips the article and does not call LLM

#### Scenario: Force reprocess
- **WHEN** user specifies --force flag
- **THEN** system reprocesses all articles regardless of existing records

### Requirement: Batch extract stocks by feed

The system SHALL support extracting stocks from all articles of a specified feed (public account).

#### Scenario: Extract from feed
- **WHEN** user runs `wchat ai extract-stocks <mp_id>`
- **THEN** system processes all articles belonging to that feed

#### Scenario: Feed not found
- **WHEN** specified mp_id does not exist
- **THEN** system displays error message

### Requirement: Output results

The system SHALL support outputting extraction results to console or file.

#### Scenario: Console output
- **WHEN** user runs command without --output flag
- **THEN** system displays results in console with Rich formatting

#### Scenario: File output
- **WHEN** user specifies --output flag with file path
- **THEN** system writes results to the specified file

### Requirement: Processing summary

The system SHALL display a summary after batch processing completes.

#### Scenario: Batch processing complete
- **WHEN** batch extraction completes
- **THEN** system displays summary including total articles processed, skipped, and stocks extracted
