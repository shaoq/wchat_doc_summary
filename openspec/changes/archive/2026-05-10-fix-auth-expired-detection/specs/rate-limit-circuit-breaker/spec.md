## MODIFIED Requirements

### Requirement: Token 失效检测不依赖 HTTP 状态码
`WeReadClient._request()` SHALL 在响应体包含 `WeReadError401` 时立即抛出 `AuthExpiredError`，不进入重试循环，不依赖 HTTP 状态码。

#### Scenario: HTTP 500 + WeReadError401 触发 AuthExpiredError
- **WHEN** `_request()` 收到 HTTP 500 且响应体包含 `WeReadError401`
- **THEN** 系统 SHALL 立即抛出 `AuthExpiredError`
- **AND** 不执行任何重试

#### Scenario: HTTP 401 + WeReadError401 仍然触发 AuthExpiredError
- **WHEN** `_request()` 收到 HTTP 401 且响应体包含 `WeReadError401`
- **THEN** 系统 SHALL 立即抛出 `AuthExpiredError`
- **AND** 不执行任何重试

#### Scenario: fetch_all 遇到 AuthExpiredError 停止批量抓取
- **WHEN** `fetch_all()` 遍历订阅列表时某订阅抛出 `AuthExpiredError`
- **THEN** 系统 SHALL 停止遍历剩余订阅
- **AND** 保持当前订阅的 batch 记录为 pending
- **AND** CLI 输出"Token 已失效，请重新登录: wchat login"
