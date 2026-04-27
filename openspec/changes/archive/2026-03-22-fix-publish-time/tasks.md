## 1. Code Fix

- [x] 1.1 Modify `_fetch_and_save_article` in `src/services/fetcher.py`
  - Add helper function `_parse_publish_time_from_api(time_str)` to parse API time format
  - Modify line 149: `publish_time=article_info.get("publish_time") or parsed.get("publish_time")`

## 2. Verification

- [ ] 2.1 Re-fetch one subscription and verify publish_time is saved
- [ ] 2.2 Test `show` command displays correct publish time
