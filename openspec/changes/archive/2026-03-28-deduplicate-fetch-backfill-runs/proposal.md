## Why

文章抓取链路已经把 `publish_time` 回填作为抓取后的最佳努力步骤接入，但当前 `fetch_all()` 会在每个订阅完成 `fetch_feed()` 后再次执行一轮相同的回填。这不会直接破坏功能，却会增加不必要的 API 调用和总执行时间。

## What Changes

- 去除单次 `fetch --all` 过程中对同一订阅重复执行的 `publish_time` 回填。
- 保持 `publish_time` 回填仍然是抓取后最佳努力步骤。
- 为批量抓取场景补充“回填至多执行一次”的测试。

## Capabilities

### New Capabilities

### Modified Capabilities
- `article-fetcher`: 调整批量抓取流程中的 `publish_time` 回填执行次数，避免同一抓取轮次重复回填。

## Impact

- **Affected code**:
  - `src/services/fetcher.py`
- **Affected tests**:
  - 需要新增批量抓取回填执行次数测试
- **Affected behaviors**:
  - `wchat fetch --all`
