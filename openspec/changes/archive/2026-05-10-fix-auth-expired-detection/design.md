## Context

`WeReadClient._request()` 在 `src/api/weread.py:146-156` 中检测 Token 失效，条件为 `status_code == 401 AND body 含 WeReadError401`。但微信读书 API 实际返回 HTTP 500 + `WeReadError401`，导致检测未命中，错误落入通用重试路径。`fetch_all()` 将其作为普通 `Exception` 处理，继续抓取下一个订阅。

下游逻辑已完备：`fetcher.py` 有 `AuthExpiredError` 的 break 分支，`subscription.py` 有"请重新登录"的用户提示。唯一缺失的是异常分类的入口。

## Goals / Non-Goals

**Goals:**
- 让 HTTP 500 + `WeReadError401` 也能触发 `AuthExpiredError`
- `fetch --all` 遇到认证失效立即停止，提示用户重新登录

**Non-Goals:**
- 不修改 `FetcherService`、CLI 层（已有正确处理）
- 不引入 pre-flight token 验证机制
- 不修改 `RateLimitError` 的检测逻辑

## Decisions

**Decision: 仅检查 body 中的 `WeReadError401`，移除状态码判断**

将检测条件从 `status_code == 401 AND "WeReadError401" in body` 改为 `"WeReadError401" in body`。

- 备选方案 A：同时检查 401 和 500 → 增加 `or status_code == 500`。更保守但冗余，`WeReadError401` 作为标识符已足够明确。
- 备选方案 B：仅检查 body → 选择此方案。`WeReadError401` 字符串是微信读书 API 的明确错误码，误判风险极低。

## Risks / Trade-offs

- [低风险] 假阳性：理论上非 401/500 响应也可能含 `WeReadError401` → 极不可能，该错误码语义唯一绑定认证失效
- [无风险] 下游代码无需改动，`AuthExpiredError` 的传播路径已经完整
