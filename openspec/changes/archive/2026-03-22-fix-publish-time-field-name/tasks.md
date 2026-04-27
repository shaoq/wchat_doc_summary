## 1. Code Fix

- [x] 1.1 Modify `_parse_publish_time` to accept both field names
  - Add `_get_publish_time_from_info` helper function
  - Check both `publishTime` and `publish_time`
  - Support integer timestamp format
- [x] 1.2 Update `_fetch_and_save_article` to use the enhanced function
  - Call `_get_publish_time_from_info` with both field names
  - Update time filtering in `fetch_feed` and `fetch_incremental`

## 2. Verification
- [ ] 2.1 Re-fetch and verify publish_time is saved correctly (blocked by API auth issue)
- [ ] 2.2 Test `show` command displays correct publish time (blocked by API auth issue)

## Additional Fixes (found during implementation)
- [x] Fixed `weReadAPIError` → `WeReadAPIError` typo
- [x] Fixed time filtering to use `_get_publish_time_from_info` instead of `datetime.fromisoformat`
- [x] Support integer timestamps in `_parse_publish_time`
