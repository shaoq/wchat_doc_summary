## Why

当前 `FetcherService` 已经承载了公众号抓取主链路，但其实现出现了职责混杂、重复定义、参数语义不一致和会话边界错误等问题。继续在现有结构上叠加抓取能力会显著提高回归风险，因此需要先完成一次围绕抓取服务本身的结构性收敛。

## What Changes

- 清理 `FetcherService` 中重复或命名错误的方法定义，恢复“一个职责对应一个公开方法”的结构。
- 显式区分全量抓取、增量抓取、公众号信息解析和发布时间回填四类能力。
- 修复发布时间回填中的参数语义、数据库会话边界和更新流程错误。
- 修复“抓取最近 N 天文章”路径中的时间过滤与提前停止翻页逻辑。
- 统一抓取服务的错误处理和返回行为，减少 CLI 及调用方对隐式分支的依赖。
- 为抓取主路径补充测试，覆盖全量抓取、增量抓取、公众号信息获取和发布时间回填。

## Capabilities

### New Capabilities
- `article-publish-time-backfill`: 为已入库但缺失发布时间的文章提供安全的发布时间回填能力。

### Modified Capabilities
- `article-fetcher`: 调整抓取服务的职责边界、时间过滤行为、增量抓取语义和错误处理规则。

## Impact

- **Affected code**:
  - `src/services/fetcher.py`
  - `src/cli.py`
  - 可能少量影响 `src/services/subscription.py`
  - 可能少量影响 `src/api/weread.py`
- **Affected tests**:
  - `tests/test_services.py`
  - 需要新增或拆分抓取服务相关测试
- **Affected behaviors**:
  - `wchat fetch --all`
  - `wchat fetch <mp_id>`
  - `wchat subscribe <article_url>`
  - 后续基于增量抓取的服务复用路径
