## Context

当前 `MarketAnalyzer.collect_news_data()` 对三类新闻输入采用同一模式：

1. 计算时间窗口
2. 直接查询本地库
3. 若为空则记为 `empty`
4. 若抛异常则记为 `error`

这对相关文章是合理的，因为文章抓取本来就是独立流程；但对财联社电报和看盘数据，系统已经具备按时间窗口直接抓远端再入库的能力，只是 `market-summary` 没有接入这一能力。结果就是在线模式下，即便远端数据可用，阶段 2 仍然可能只显示 `0 条`。

另一个结构性问题是：`CLSTelegraphService.ingest_telegraphs()` 和 `CLSWatchService.ingest_watch_data()` 当前都只返回 `(inserted, skipped)`。远端空结果、抓取异常、以及抓到但全部被去重跳过这三种情况很容易收敛成相同的 `(0, 0)`，上层无法判断自动补抓到底是“成功但无数据”还是“失败”。

因此这次变更不应只在 `collect_news_data()` 里简单补一层 `ingest_*` 调用，而是需要同时补齐 CLS 抓取结果 contract 与 CLI 展示语义。

## Goals / Non-Goals

**Goals:**
- 在线模式下，当本地 CLS 电报或看盘数据为空时，自动执行一次按 summary 窗口的远端抓取并回查本地。
- 让新闻阶段能区分三种结果：本地或补抓后成功命中、抓取成功但仍为空、自动补抓失败。
- 保持 `offline=True` 时完全不触发远端 CLS 抓取。
- 在 CLI 中明确展示 CLS 来源最终状态，避免用户只看到 `0 条` 却不知道系统是否已经尝试补抓。

**Non-Goals:**
- 不改变相关文章的获取策略，不在 `market-summary` 中自动抓文章。
- 不复用 `wchat cls fetch-*` CLI 的“回溯小时数”命令语义作为市场总结内部 contract。
- 不改变市场总结文章窗口、电报窗口和看盘窗口的业务定义。
- 不在本次变更中引入并发补抓或后台任务机制。

## Decisions

### 1. 自动补抓只放在 `MarketAnalyzer.collect_news_data()` 中

选择：把“查本地 -> 查空则自动补抓 -> 再回查”的控制流放进 `collect_news_data()`，而不是 CLI 层，也不是复用 `cls` 命令。

理由：
- `collect_news_data()` 已持有电报窗口和看盘窗口，是最清楚业务时间边界的位置。
- CLI 层只负责展示，不适合承载新闻聚合回退逻辑。
- `cls fetch-*` 命令的 `--hours` 是人工运维语义，不等于 `market-summary` 的精确窗口。

备选方案：
- 在 `src/cli/ai.py` 里先查空再直接调 service。放弃原因：会把聚合逻辑与 CLI 编排耦合。
- 在 CLS service 内部隐式“查空即抓”。放弃原因：service 本身是通用查询/入库层，不应强绑定 `market-summary` 场景。

### 2. 自动补抓仅在在线模式且本地为空时触发

选择：
- 本地已有数据：直接使用，不触发补抓
- `offline=True`：本地为空也不补抓
- 仅当 `offline=False` 且本地为空时，才触发补抓

理由：
- 这保持“缓存优先”语义，不会让每次 `market-summary` 都重新抓 CLS。
- 离线模式 contract 必须保持纯本地，否则会破坏用户对 `--offline` 的预期。

备选方案：
- 在线模式每次都补抓。放弃原因：无谓增加远端请求与运行时间，也削弱本地缓存价值。

### 3. CLS 抓取结果 contract 需要显式区分 `ok / empty / error`

选择：为 `ingest_telegraphs()` 和 `ingest_watch_data()` 提供更丰富的结果语义，至少包括：
- 抓取状态：`ok | empty | error`
- 远端抓取数量
- 本地新增/跳过数量

理由：
- 仅靠 `(inserted, skipped)` 无法让上层判断自动补抓后的真实结果。
- 自动补抓后的 CLI 状态必须能够映射到“补抓后成功”“补抓后为空”“补抓失败”。

备选方案：
- 继续沿用 `(inserted, skipped)`，由上层二次查询猜测状态。放弃原因：无法可靠区分远端空结果和抓取异常。

### 4. 新闻阶段状态仍以最终数据可用性为主，但要保留自动补抓过程可见性

选择：`news_data` 的 `sources_status` 仍然只表示最终归一化状态 `ok / empty / error`，同时增加额外元数据表示该来源是否触发过自动补抓，以及补抓结果摘要。

理由：
- 这样能兼容现有 CLI 状态体系，不必重做整套 `_get_news_status_items()`。
- 同时也能让阶段 2 输出在 `empty` 场景下区分“直接本地空”与“自动补抓后仍空”。

备选方案：
- 把 `sources_status` 扩成更多状态，例如 `fetched_ok`、`fetched_empty`。放弃原因：会扩大现有状态渲染和测试改动面。

## Risks / Trade-offs

- [自动补抓增加阶段 2 耗时] → 仅在本地为空时触发，并限制在已有 summary 时间窗口内。
- [远端抓取结果 contract 改动会影响既有 `cls` 命令实现] → 保持 CLI 可继续使用，只是在 service 返回值上增加结构化信息或新增 helper，避免破坏现有调用方。
- [补抓后仍为空时，用户可能误以为系统没有执行] → 通过阶段 2 文案或附加 detail 明确显示“本地无数据，已自动抓取，结果仍为空”。
- [历史测试假设 `collect_news_data()` 只读本地] → 需要同步更新测试契约，明确在线/离线两种路径的差异。

## Migration Plan

1. 扩展 CLS 抓取服务的结果表达能力，能区分 `ok / empty / error`。
2. 在 `collect_news_data()` 中加入在线模式的本地查空自动补抓和回查逻辑。
3. 为 `news_data` 增加自动补抓过程元数据，并调整 CLI 阶段 2/预检输出。
4. 更新单元测试与 CLI 流程测试，覆盖本地命中、自动补抓成功、自动补抓后为空、自动补抓失败、离线跳过补抓等场景。

## Open Questions

- 自动补抓过程信息是直接进入 `sources_status`，还是通过单独的 `fetch_attempts` / `auto_fetch` 字段承载更合适。
- 当自动补抓抓到的数据全部因去重被跳过、但本地回查仍为空时，CLI 是否应单独显示“抓取成功但无新数据”，还是统一归类为 `empty`。
