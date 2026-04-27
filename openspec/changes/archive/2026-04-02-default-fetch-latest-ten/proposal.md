## Why

当前 `wchat fetch` 默认按“最近 5 天”抓取，但这一语义并没有下推到上游接口，而是先整页拉取文章列表，再在本地按发布时间过滤。结果是用户即使只想拿最近几篇文章，只要上游第一页里混入一条坏记录，整个抓取就会因远端 `500 -> WeReadError400` 失败，无法满足“快速同步最近内容”的真实使用场景。

结合这次 `MP_WXS_3917032509` 的故障分析，可以确认用户的默认需求其实更接近“抓最近的少量新文章”，而不是按天数做近似过滤。因此需要把默认抓取 contract 收敛为“最新 10 条”，并补上对上游异常列表项的容错与可观测性。

## What Changes

- 将 `wchat fetch` 的默认抓取语义从“最近 5 天”调整为“最新 10 条文章”。
- 为抓取服务增加“按文章条数限制”的行为约束，确保默认路径最多只处理最新 10 条文章，而不是依赖本地时间过滤。
- 调整文章列表抓取失败时的处理策略，支持在上游列表接口因单条坏记录失败时提供更明确的错误上下文，并为后续降级重试或缩小抓取窗口预留 contract。
- 更新 CLI 文案、规格与测试，确保默认行为、参数优先级和异常可观测性一致。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `article-fetcher`: 默认抓取 contract 从“最近 5 天”改为“最新 10 条”，并增加对上游文章列表异常项的容错与更清晰的错误反馈要求。

## Impact

- 受影响代码:
  - `src/cli/subscription.py`
  - `src/services/fetcher.py`
  - `src/api/weread.py`
- 受影响测试:
  - `tests/test_services.py`
  - `tests/test_api.py`
  - 视实现方式可能补充 `tests/test_fetcher_integration.py`
- 受影响行为:
  - `wchat fetch MP_WXS_xxx`
  - `wchat fetch --all`
  - `wchat fetch --days N`
  - `wchat fetch --full`
