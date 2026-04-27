## Why

当前批量抓取路径优先追求“尽快同步”，但缺少限流前的主动预防与异常空结果识别，导致 `wchat fetch --all` 容易触发 WeRead 临时封禁，也会把上游临时空响应误判为“成功抓到 0 篇”。这个问题已经影响抓取稳定性和用户对同步结果的判断，需要将批量抓取语义调整为“稳态优先”。

## What Changes

- 将 `wchat fetch --all` 的默认无范围抓取语义调整为保守增量同步，而不是对每个订阅固定抓取最新 10 条。
- 为批量抓取增加主动节流、订阅间等待、抖动和异常后的退避策略，优先降低触发 WeRead 限流的概率。
- 为文章列表空页增加可疑空响应保护，避免第一次空列表就被当作正常完成。
- 收紧文章列表响应校验，异常格式或无效载荷不再静默归一化为“0 篇”。
- 改进抓取结果统计与 CLI 展示，区分“上游返回为空”“本次无新增”“文章已存在”“保存失败”“可疑空页重试后放弃”等状态。
- 限制 `sync_time` 的更新时间机，避免可疑空跑被记录为成功同步。

## Capabilities

### New Capabilities

- `batch-fetch-throttling`: 批量抓取的主动节流、退避和稳态同步策略

### Modified Capabilities

- `article-fetcher`: 调整批量默认抓取语义、空页判定、结果统计和同步成功条件

## Impact

- **代码**: `src/cli/subscription.py`, `src/services/fetcher.py`, `src/api/weread.py`, `src/api/providers/*`
- **行为**: `wchat fetch --all` 默认行为将变慢但更保守；CLI 抓取统计将更细
- **规格**: 新增 `batch-fetch-throttling` spec，并修改 `article-fetcher` spec
- **依赖**: 无新增外部依赖，继续使用现有 `asyncio` / `httpx`
