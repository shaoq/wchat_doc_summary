## Why

当前 fetch 脚本每次抓取的文章数量上限为 50 篇（5 页 × 每页 10 篇），无法满足需要抓取更多历史文章的场景。通过增加 `page_size` 参数，可以在相同页数限制下获取更多文章，提升抓取效率。

## What Changes

- 在 `WeReadClient.get_articles()` 中增加 `page_size` 参数，支持自定义每页返回的文章数量
- 在 `FetcherService.fetch_feed()` 中增加 `page_size` 参数透传
- 在配置文件中增加 `fetch_page_size` 默认值（默认 50）
- 默认抓取上限从 50 篇提升到 250 篇（5 页 × 每页 50 篇）

## Capabilities

### New Capabilities

无新增 capability。

### Modified Capabilities

无修改的 capability（这是纯实现层面的优化，不改变功能需求）。

## Impact

- **config/settings.py**: 新增 `fetch_page_size` 配置项
- **src/api/weread.py**: `get_articles()` 方法签名变更，增加 `page_size` 参数
- **src/services/fetcher.py**: `fetch_feed()` 方法签名变更，增加 `page_size` 参数
- **向后兼容**: 所有新参数都有默认值，不影响现有调用
