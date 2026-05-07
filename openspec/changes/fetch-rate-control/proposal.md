## Why

`wchat fetch --all` 频繁触发微信读书 API 限流。当前仅在订阅切换时有 3~5s 间隔，订阅内部的列表翻页、文章内容抓取、发布时间回填均无任何间隔控制，导致突发式密集请求。用户实际使用中反复遇到限流中断，无法完成批量抓取。

## What Changes

- 在列表翻页之间增加可配置间隔（默认 6s）
- 在单篇文章内容抓取之间增加可配置间隔（默认 6s）
- 调大订阅间基础等待（从 3~5s 提升到 8~12s）
- 新增全局滑动窗口速率限制器，硬性限制每分钟最大请求数（默认 12 次/分钟）
- 发布时间回填操作同样纳入速率控制
- 所有间隔参数可通过 settings 配置，无需改代码
- 增加实时进度输出：订阅进度、翻页/文章抓取状态、等待提示，避免用户误以为卡死

## Capabilities

### New Capabilities
- `fetch-rate-throttle`: 多层请求间隔控制（列表页、文章内容、订阅间）+ 全局滑动窗口速率限制器
- `fetch-progress-reporting`: 抓取过程的实时进度回调机制与 CLI 进度输出

### Modified Capabilities
- `article-fetcher`: 集成速率限制器和进度回调，在所有请求循环中插入等待
- `rate-limit-circuit-breaker`: 配合主动限速，减少被动触发限流熔断的频率

## Impact

- `src/services/fetcher.py`: 核心改动 — 所有请求循环增加间隔，新增回调参数
- `src/utils/` 或 `src/services/`: 新增速率限制器模块
- `config/settings.py`: 新增 6 个间隔/速率配置项
- `src/cli/subscription.py`: 进度输出改造
- 抓取耗时会显著增加（从 ~2 分钟增至 ~7 分钟），但换来稳定性和成功率
