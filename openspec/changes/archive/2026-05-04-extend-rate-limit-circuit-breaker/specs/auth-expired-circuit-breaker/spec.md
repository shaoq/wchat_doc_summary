## ADDED Requirements

### Requirement: AuthExpiredError 异常定义
系统 SHALL 定义 `AuthExpiredError` 异常类，继承自 `WeReadAPIError`，用于标识 WeRead 代理的 Token 失效响应。

#### Scenario: AuthExpiredError 包含原始错误信息
- **WHEN** WeRead 代理返回 HTTP 401 且 response 包含 `WeReadError401`
- **THEN** 系统 SHALL 抛出 `AuthExpiredError`，携带 status_code 和 response_text

### Requirement: Token 失效响应识别与立即中断
`WeReadClient._request()` SHALL 在收到 Token 失效响应时立即抛出 `AuthExpiredError`，不进入重试循环。

#### Scenario: Token 失效时不重试
- **WHEN** `_request()` 收到 HTTP 401 且响应体包含 `WeReadError401`
- **THEN** 系统 SHALL 立即抛出 `AuthExpiredError`
- **AND** 不执行任何重试

### Requirement: 单订阅抓取 Token 失效时直接停止
`FetcherService.fetch_feed()` SHALL 捕获 `AuthExpiredError` 后直接上抛异常，与 `RateLimitError` 行为一致。

#### Scenario: fetch_feed Token 失效时停止
- **WHEN** `fetch_feed()` 内部调用 Provider 时抛出 `AuthExpiredError`
- **THEN** 系统 SHALL 停止当前订阅的抓取
- **AND** 将 `AuthExpiredError` 上抛给调用方

### Requirement: 批量抓取 Token 失效时全局熔断
`FetcherService.fetch_all()` SHALL 在任一订阅遇到 `AuthExpiredError` 时停止遍历剩余订阅，返回已完成的部分结果。

#### Scenario: fetch_all Token 失效时保存部分结果
- **WHEN** `fetch_all()` 遍历订阅列表时某订阅抛出 `AuthExpiredError`
- **THEN** 系统 SHALL 停止遍历剩余订阅
- **AND** 返回已成功抓取的订阅结果

### Requirement: CLI Token 失效友好提示
CLI `fetch` 命令 SHALL 在捕获 `AuthExpiredError` 时输出"Token 已失效，请重新登录"的提示。

#### Scenario: 单订阅 fetch Token 失效提示
- **WHEN** `wchat fetch <mp_id>` 触发 `AuthExpiredError`
- **THEN** CLI SHALL 输出"Token 已失效，请重新登录: wchat login"

#### Scenario: 批量 fetch --all Token 失效提示
- **WHEN** `wchat fetch --all` 触发 `AuthExpiredError`
- **THEN** CLI SHALL 输出已完成订阅数量和总数
- **AND** 输出"请重新登录: wchat login"
