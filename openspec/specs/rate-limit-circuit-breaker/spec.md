# rate-limit-circuit-breaker

## ADDED Requirements

### Requirement: RateLimitError 异常定义
系统 SHALL 定义 `RateLimitError` 异常类，继承自 `WeReadAPIError`，用于标识 WeRead 代理的限流响应。

#### Scenario: RateLimitError 包含原始错误信息
- **WHEN** WeRead 代理返回 HTTP 500 且 response 包含 `WeReadError400`
- **THEN** 系统 SHALL 抛出 `RateLimitError`，携带 status_code 和 response_text

### Requirement: 限流响应识别与立即中断
`WeReadClient._request()` SHALL 在收到限流响应时立即抛出 `RateLimitError`，不进入重试循环。

#### Scenario: 限流时不重试
- **WHEN** `_request()` 收到 HTTP 500 且响应体包含 `WeReadError400`
- **THEN** 系统 SHALL 立即抛出 `RateLimitError`
- **AND** 不执行任何重试

#### Scenario: 非 WeRead Provider 不受影响
- **WHEN** 使用 wechat2rss Provider
- **THEN** 不存在 `RateLimitError` 的抛出路径，行为不变

### Requirement: 单订阅抓取限流时直接停止
`FetcherService.fetch_feed()` SHALL 捕获 `RateLimitError` 后直接上抛异常，不尝试 narrow-retry 缩窗口重试。

#### Scenario: fetch_feed 限流时停止
- **WHEN** `fetch_feed()` 内部调用 Provider 时抛出 `RateLimitError`
- **THEN** 系统 SHALL 停止当前订阅的抓取
- **AND** 将 `RateLimitError` 上抛给调用方

#### Scenario: _get_latest_articles_with_retry 限流时不上抛重试
- **WHEN** `_get_latest_articles_with_retry()` 中某次请求抛出 `RateLimitError`
- **THEN** 系统 SHALL 直接上抛，不尝试缩小 page_size 重试

### Requirement: 批量抓取限流时全局熔断
`FetcherService.fetch_all()` SHALL 在任一订阅遇到 `RateLimitError` 时停止遍历剩余订阅，返回已完成的部分结果。

#### Scenario: fetch_all 限流时保存部分结果
- **WHEN** `fetch_all()` 遍历订阅列表时某订阅抛出 `RateLimitError`
- **THEN** 系统 SHALL 停止遍历剩余订阅
- **AND** 返回已成功抓取的订阅结果
- **AND** 在返回的 results 中为未处理的订阅设置空列表

#### Scenario: fetch_all 第一个订阅就限流
- **WHEN** `fetch_all()` 的第一个订阅就触发 `RateLimitError`
- **THEN** 系统 SHALL 返回空结果字典
- **AND** CLI 输出"0/N 个订阅已完成"

### Requirement: CLI 限流友好提示
CLI `fetch` 命令 SHALL 在捕获 `RateLimitError` 时输出清晰的限流提示，包含已完成/总数、手动恢复指引。

#### Scenario: 单订阅 fetch 限流提示
- **WHEN** `wchat fetch <mp_id>` 触发 `RateLimitError`
- **THEN** CLI SHALL 输出限流提示，如"已被限流，请稍后重试: wchat fetch <mp_id>"

#### Scenario: 批量 fetch --all 限流提示
- **WHEN** `wchat fetch --all` 触发 `RateLimitError`
- **THEN** CLI SHALL 输出已完成订阅数量和总数，如"已被限流，已完成 3/8 个订阅"
- **AND** 输出恢复指引，如"请稍后重试: wchat fetch --all"
