## Why

WeRead 代理服务 (`weread.111965.xyz`) 在请求过于频繁时返回 `500 WeReadError400`，触发限流。当前代码对限流响应没有识别能力，仍会立即重试 3 次（无退避间隔），并在 `fetch_all` 批量模式下继续请求后续订阅，导致雪上加霜、全部订阅抓取失败。

## What Changes

- 在 `WeReadClient._request()` 中识别限流响应（`status=500` + `WeReadError400`），抛出专用的 `RateLimitError` 异常，**不进入重试循环**
- `FetcherService.fetch_feed()` 捕获 `RateLimitError` 后直接上抛，不尝试 narrow-retry 缩窗口重试
- `FetcherService.fetch_all()` 捕获 `RateLimitError` 后停止遍历剩余订阅，返回已完成的部分结果
- CLI `fetch` 命令捕获 `RateLimitError`，输出友好的限流提示（已完成/未完成的订阅数量）及手动恢复指引

## Capabilities

### New Capabilities
- `rate-limit-circuit-breaker`: WeRead API 限流识别与全局熔断机制，包含限流异常定义、熔断传播逻辑和用户提示

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- **代码**: `src/api/weread.py`（新增异常 + 识别逻辑）、`src/services/fetcher.py`（捕获与熔断传播）、`src/cli/subscription.py`（用户提示）
- **依赖**: 无新增依赖
- **行为变更**: 限流时不再重试，立即停止并提示用户手动恢复
