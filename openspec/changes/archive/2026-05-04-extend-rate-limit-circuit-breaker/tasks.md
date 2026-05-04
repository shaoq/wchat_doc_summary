## 1. 异常定义与检测

- [x] 1.1 在 `src/api/weread.py` 中定义 `AuthExpiredError` 异常类（继承 `WeReadAPIError`）
- [x] 1.2 在 `WeReadClient._request()` 中增加 401 + `WeReadError401` 检测，抛出 `AuthExpiredError`，不重试

## 2. 业务层扩展

- [x] 2.1 在 `FetcherService` 中增加 `AuthExpiredError` 的 import 和 catch 逻辑（`fetch_feed`、`fetch_all`、`_get_latest_articles_with_retry`），与 `RateLimitError` 行为一致

## 3. CLI 提示

- [x] 3.1 在 `src/cli/subscription.py` 的 `fetch` 命令中，捕获 `AuthExpiredError` 并输出"Token 已失效，请重新登录: wchat login"

## 4. 测试

- [x] 4.1 补充 `AuthExpiredError` 单元测试：401 检测、不重试
- [x] 4.2 补充 `fetch_feed` / `fetch_all` 的 Token 失效熔断测试
