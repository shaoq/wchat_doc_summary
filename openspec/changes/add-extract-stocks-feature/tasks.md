## 1. Data Model

- [x] 1.1 Add `ArticleProcessing` model to `src/models/schema.py`
- [x] 1.2 Add database migration support (if needed)

## 2. Service Layer

- [x] 2.1 Add `EXTRACT_STOCKS_PROMPT` template to `src/services/ai_processor.py`
- [x] 2.2 Add `extract_stocks` method to `AIProcessor` class
- [x] 2.3 Add `_get_processed_articles` helper method to query processed article IDs
- [x] 2.4 Add `_record_processing` helper method to save processing results

## 3. CLI

- [x] 3.1 Add `extract_stocks` command to `ai` command group in `src/cli.py`
- [x] 3.2 Implement `--output` parameter for file export
- [x] 3.3 Implement `--force` flag to reprocess articles
- [x] 3.4 Add progress display and summary output

## 4. Testing

- [ ] 4.1 Add unit tests for `ArticleProcessing` model
- [ ] 4.2 Add unit tests for `extract_stocks` method
- [ ] 4.3 Add integration tests for CLI command

## 5. Documentation

- [ ] 5.1 Update README or help text with new command usage
