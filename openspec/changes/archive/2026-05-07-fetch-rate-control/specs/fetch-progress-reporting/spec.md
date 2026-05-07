## ADDED Requirements

### Requirement: 进度事件数据结构
系统 SHALL 定义 `FetchProgressEvent` 数据类，包含 type、mp_id、feed_name、detail 字段，用于 fetcher 层向 CLI 层传递进度信息。

#### Scenario: 事件类型
- **WHEN** fetcher 在关键节点发送进度事件
- **THEN** 事件 type SHALL 为以下之一: "subscription_start"、"page_fetch"、"article_fetch"、"article_skip"、"subscription_done"、"waiting"、"rate_limited"

### Requirement: 回调参数传递
FetcherService 的 `fetch_all()` 和 `_fetch_feed_summary()` SHALL 接受可选的 `on_progress: Callable[[FetchProgressEvent], None] | None` 参数，默认 None 保持向后兼容。

#### Scenario: 传入回调时触发
- **WHEN** on_progress 不为 None 且 fetcher 到达关键节点
- **THEN** SHALL 调用 on_progress(event) 传递进度事件

#### Scenario: 未传入回调时静默
- **WHEN** on_progress 为 None
- **THEN** fetcher 行为与改动前完全一致，不产生任何额外输出

### Requirement: 订阅级进度输出
CLI fetch --all 命令 SHALL 实时显示当前正在抓取的订阅名称和序号进度。

#### Scenario: 显示订阅进度
- **WHEN** 开始抓取某订阅
- **THEN** CLI SHALL 输出 `[N/total] 订阅名称` 格式的进度

#### Scenario: 显示翻页进度
- **WHEN** 获取某页列表完成
- **THEN** CLI SHALL 输出 "获取列表页 N/M ✓ (X 篇)" 格式的信息

### Requirement: 文章级进度输出
CLI SHALL 实时显示每篇文章的抓取状态。

#### Scenario: 新文章抓取
- **WHEN** 成功抓取并保存一篇新文章
- **THEN** CLI SHALL 输出 "抓取: 文章标题 (新)"

#### Scenario: 已存在文章跳过
- **WHEN** 文章已存在于数据库
- **THEN** CLI SHALL 输出 "跳过: 文章标题 (已存在)"

#### Scenario: 文章抓取失败
- **WHEN** 文章抓取失败
- **THEN** CLI SHALL 输出 "失败: 文章标题"

### Requirement: 等待状态提示
当 fetcher 因间隔或限速进入等待时，CLI SHALL 输出等待提示。

#### Scenario: 间隔等待提示
- **WHEN** 因请求级间隔进入等待
- **THEN** CLI SHALL 输出 "⏳ 等待 X.Xs 后继续..."

#### Scenario: 全局限速等待提示
- **WHEN** 因全局 RateLimiter 触发等待
- **THEN** CLI SHALL 输出 "⏳ 全局限速: 已达 N 次/分钟，等待 Xs..."

#### Scenario: 订阅间等待提示
- **WHEN** 订阅切换进入等待
- **THEN** CLI SHALL 输出 "⏳ 切换订阅，等待 X.Xs..."

### Requirement: 订阅完成摘要
每个订阅抓取完成后，CLI SHALL 输出该订阅的抓取摘要。

#### Scenario: 摘要输出
- **WHEN** 某订阅抓取完成
- **THEN** CLI SHALL 输出 "完成: X 篇新增, Y 篇已存在" 格式的摘要（复用已有的 _print_fetch_summary 逻辑）
