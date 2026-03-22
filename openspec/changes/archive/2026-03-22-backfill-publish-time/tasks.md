## 1. Code Fix

- [x] 1.1 Modify `_fetch_and_save_article` in `src/services/fetcher.py`
  - Add `_get_publish_time_from_info` method
  - Add parameter to check both `publishTime` and `publish_time`
  - Keep backward compatibility

- [x] 1.2 Update `_fetch_and_save_article` to use the enhanced function
  - Call `_get_publish_time_from_info` with both field names

## 2. Verification

- [x] 2.1 Re-fetch one subscription and verify publish_time is saved correctly
- [x] 2.2 Test `show` command displays correct publish time
- [x] 3.1 Add `wchat backfill <mp_id>` command
- [x] 4.2 Test manual backfill command
