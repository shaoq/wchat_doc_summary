## Why

当前文章抓取链路对发布时间存在不一致的时区语义：`weread` provider 返回的 Unix 时间戳先被解析为 UTC aware datetime，再直接写入无时区的 SQLite `DateTime` 字段，最终在 CLI 和市场总结窗口查询中被当作本地时间展示和过滤，导致文章发布时间普遍早 8 小时。

这个问题已经影响到用户可见结果和下游分析准确性：文章列表、文章详情、增量抓取比较以及 `market-summary` 的文章窗口判断都会基于错误时间运行。因此需要尽快收敛发布时间 contract，统一为“入库前转换为上海时区的无时区时间”，并补上历史错误数据修复要求。

## What Changes

- 将文章抓取链路中的 `publish_time` 入库 contract 明确为“上海时区本地时间（naive datetime）”。
- 调整 provider 时间解析逻辑，对 Unix 时间戳和带时区字符串在入库前统一转换到 `Asia/Shanghai`，避免 UTC 时间直接写入数据库。
- 为历史已入库的错误文章时间增加可执行的修复策略，重点覆盖 `weread` provider 已保存的 UTC naive 错误记录。
- 明确抓取、增量比较、文章展示和市场总结文章窗口都基于统一后的上海时区发布时间语义运行。
- 更新相关测试，覆盖 Unix 时间戳解析、入库值、历史修复和窗口查询回归。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `article-fetcher`: 文章发布时间的解析、入库、回填和下游时间比较语义将统一改为上海时区本地时间。

## Impact

- 受影响代码:
  - `src/services/fetcher.py`
  - `src/api/providers/weread_provider.py`
  - `src/api/article.py`
  - 视实现方式可能涉及 `src/cli/article.py` 与依赖 `Article.publish_time` 的查询逻辑
- 受影响数据:
  - `articles.publish_time`
  - 现有 `provider='weread'` 的历史文章记录需要修复
- 受影响行为:
  - `wchat fetch`
  - `wchat article`
  - `wchat ai market-summary` 的文章窗口命中结果
- 受影响测试:
  - `tests/test_services.py`
  - `tests/test_fetcher_integration.py`
  - 视实现方式补充市场总结相关回归测试
