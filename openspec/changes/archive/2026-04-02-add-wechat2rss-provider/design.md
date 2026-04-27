## Context

当前 `wchat` 的抓取链路把“文章列表获取”和“正文抓取/解析/入库”绑在了同一条 WeRead 专有路径上：

1. 通过 WeRead 代理从 `mp_id` 获取文章列表
2. 从列表项中取 `article_id`
3. 直接请求 `https://mp.weixin.qq.com/s/{article_id}` 获取正文
4. 落库并进入后续 AI 流程

这条路径的问题不在正文抓取，而在列表获取。最近的排查已经确认，某些公众号在上游列表接口阶段会稳定触发 `id(...): WeReadError400`，即使缩小 `pageSize` 或切页也无法恢复。换句话说，系统当前被单一列表源的故障完全锁死，而项目后半段能力实际上仍然可用。

同时，候选替代源 `Wechat2RSS` 提供的输入更接近“文章 URL / feed item / 发布信息”，而不是 WeRead 风格的 `article_id`。这意味着引入新源不能只是替换一个 HTTP endpoint，而必须把“列表 Provider”从抓取服务中抽出来，并让正文抓取入口接受完整 URL。

## Goals / Non-Goals

**Goals:**
- 将文章列表获取从 WeRead 专有实现中解耦，定义统一的列表 Provider 抽象。
- 接入 `Wechat2RSS` 作为首个新 Provider，支持从外部 API 获取公众号文章列表。
- 保持现有正文抓取、HTML 解析、落库和 AI 后处理链路尽量不变。
- 让 `FetcherService` 能根据配置选择列表 Provider，而不是写死到 WeRead。
- 扩展订阅与文章模型，记录 Provider 相关元数据，为后续多源并存打基础。

**Non-Goals:**
- 不在本次变更中移除现有 WeRead 实现；它仍可作为兼容或备用 Provider 保留。
- 不重做现有 AI 处理、导出、展示、市场分析等后续能力。
- 不在本次变更中同时接入多个新 Provider；第一版只落 `Wechat2RSS`。
- 不试图解决所有外部源的反爬、频控和部署问题；本次只定义接入 contract 与首个实现。

## Decisions

### 1. 新增统一 `ArticleListProvider` 抽象，而不是在 `FetcherService` 中直接分支 if/else

选择：为文章列表获取定义统一 Provider 接口，`FetcherService` 只依赖抽象返回的标准文章项，而不直接感知每个外部源的 HTTP 细节。

理由：
- 这能把“外部源不稳定”隔离在 Provider 边界内，不让 `FetcherService` 再承担适配责任。
- 第一版只接 `Wechat2RSS`，但抽象完成后，后续接 RSS feed、URL inbox 或其他源的成本会显著下降。
- 这与当前系统已存在的“后半段通用、前半段脆弱”的问题结构完全对齐。

备选方案：
- 直接在 `FetcherService` 里增加 `if provider == "wechat2rss"` 分支。放弃原因：短期更快，但会让抓取服务继续承担 provider 适配复杂度，后续不可维护。

### 2. 统一文章列表项结构以 `url` 为核心，而不是继续假设所有源都有 `article_id`

选择：Provider 输出统一文章项，核心字段至少包括：
- `title`
- `url`
- `publish_time`
- `cover`
- `external_id`
- `provider`
- 可选 `content_html`

正文抓取入口应优先接受完整文章 URL；若外部源只给 `article_id`，再退化为现有 `/s/{article_id}` 拼接方式。

理由：
- `Wechat2RSS` 和其他 feed 型来源天然更稳定地提供 URL，而不是可直接复用的微信短 ID。
- URL 是最接近真实文章资源的通用主键，适合做跨 Provider 的 dedup 基础。
- 这样可以保住你现有正文抓取与解析逻辑，只是在入口层做兼容扩展。

备选方案：
- 继续把 `article_id` 设为列表源必须输出字段。放弃原因：会把未来所有 Provider 强行拉回 WeRead 风格，抽象失效。

### 3. 第一版配置驱动 Provider 选择，不优先新增复杂 CLI 命令

选择：通过配置项选择 Provider，例如：
- `ARTICLE_LIST_PROVIDER=weread|wechat2rss`
- `WECHAT2RSS_BASE_URL=...`
- `WECHAT2RSS_TOKEN=...`

现有 CLI 命令 `subscribe` / `fetch` 保持不变。

理由：
- 当前用户心智已经围绕 `wchat subscribe` 和 `wchat fetch` 建立，第一版不需要因为 Provider 接入而重做命令面。
- Provider 切换更适合做环境配置，而不是一开始就把复杂度暴露给 CLI。
- 能最小化对现有使用方式的破坏，同时留出未来新增 `provider test` 等命令的空间。

备选方案：
- 立即新增 `--provider` 命令参数。放弃原因：第一版不是必须，且会让 CLI 和服务层同时扩散复杂度。

### 4. 通过新增 Provider 元数据字段支持多源，而不是挤压现有 `mp_id/article_id`

选择：
- `feeds` 需要新增 provider 相关字段，例如 `provider`、`provider_feed_id`、`provider_meta`
- `articles` 需要新增或明确 provider 相关字段，例如 `provider`、`provider_item_id`
- `original_url` 在多源模式下成为重要的 dedup 依据

理由：
- 现有 `Feed.mp_id` 和 `Article.article_id` 都默认承载了 WeRead 世界观，不适合继续同时兼容外部 feed item id、文章 URL 和本地唯一键。
- 如果不增加 Provider 元数据，后续多源并存时会很快出现标识冲突和迁移歧义。
- 第一版即使只接 `Wechat2RSS`，也应把模型边界一次画对。

备选方案：
- 暂时复用 `article_id` 存任意外部 ID。放弃原因：短期省事，长期会让已有语义完全混乱。

### 5. 订阅解析分两步：先保留现有 `subscribe(url)` 体验，再让解析能力可由 Provider 实现

选择：现有 `subscribe(url)` 命令不变，但解析公众号信息的实现不再默认只能走 WeRead。Provider 或 resolver 层应能根据 URL 获取订阅标识和名称，必要时允许 `Wechat2RSS` 参与解析。

理由：
- 用户已经习惯通过文章 URL 订阅公众号，这个体验没有必要因为 Provider 改造而倒退。
- `Wechat2RSS` 的 `/addurl` 能力与当前订阅方式天然兼容，适合作为替代解析来源。
- 将“订阅解析”和“文章列表获取”都纳入 Provider 边界，才能真正摆脱 WeRead 单点。

备选方案：
- 第一版只做 `fetch` 走新 Provider，`subscribe` 仍完全绑定 WeRead。放弃原因：会留下入口分裂，后续迁移更痛。

## Risks / Trade-offs

- [外部 Provider 字段不稳定或语义变化] → 通过统一 Provider DTO 做边界隔离，尽量不让下游业务层直接依赖原始返回字段。
- [数据库新增 Provider 字段会带来迁移成本] → 先设计为向后兼容字段，保留原有 `mp_id/article_id` 读写路径，逐步迁移。
- [URL 作为主要 dedup 依据可能受微信链接规范影响] → 在 dedup 设计中同时保留 `provider_item_id` 和归一化 URL，避免单一键过脆。
- [引入 `Wechat2RSS` 后仍可能遇到外部源不可用] → 本次设计保留 WeRead 兼容 Provider，不把系统再次绑死在新单点上。
- [第一版同时改 Provider、抓取入口、数据模型，范围较大] → 实施上拆为 provider 抽象、正文 URL 支持、模型字段迁移、配置接入四步，降低单次改动风险。

## Migration Plan

1. 定义统一 `ArticleListProvider` 接口与标准文章项结构。
2. 实现 `Wechat2RSSProvider`，并通过配置项注入到抓取服务。
3. 扩展正文抓取入口，使其支持完整文章 URL。
4. 扩展 `Feed` / `Article` 模型与数据库 schema，记录 provider 相关字段。
5. 将 `FetcherService` 改为从 Provider 获取文章列表，再复用现有正文抓取/入库逻辑。
6. 调整 `subscribe` 解析路径，使其可由 Provider/Resolver 完成公众号识别。
7. 补齐 Provider、抓取流程和兼容性测试。

回滚策略：
- 若 `Wechat2RSS` 接入不稳定，可保留抽象层与模型字段，仅将配置默认值切回 `weread`，不必回滚全部架构调整。

## Open Questions

- `Wechat2RSS` 第一版应优先接 `/api/query` 还是 feed JSON 输出，哪一条字段稳定性更好。
- `Article.article_id` 是否需要在本次变更中改名或降级语义，还是仅通过新增字段完成兼容。
- 是否要在 CLI 上显式增加 `provider` 诊断命令，还是先仅通过配置与日志管理。
