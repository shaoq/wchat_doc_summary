## 1. 异常定义与限流识别

- [x] 1.1 在 `src/api/weread.py` 中定义 `RateLimitError` 异常类（继承 `WeReadAPIError`）
- [x] 1.2 在 `WeReadClient._request()` 中，HTTP 响应检查阶段增加限流识别：status=500 且 response 包含 `WeReadError400` 时直接抛出 `RateLimitError`，不进入重试循环

## 2. 业务层熔断传播

- [x] 2.1 在 `FetcherService._get_latest_articles_with_retry()` 中，将 `RateLimitError` 排除在 narrow-retry 循环之外，捕获后直接上抛
- [x] 2.2 在 `FetcherService.fetch_feed()` 中，确保 `RateLimitError` 从 try 块中上抛（不吞异常）
- [x] 2.3 在 `FetcherService.fetch_all()` 中，捕获 `RateLimitError` 后停止遍历，返回已完成的部分结果

## 3. CLI 用户提示

- [x] 3.1 在 `src/cli/subscription.py` 的 `fetch` 命令中，捕获 `RateLimitError` 并输出友好提示（已完成/总数、恢复指引）

## 4. 测试

- [x] 4.1 补充 `RateLimitError` 的单元测试：限流识别、不重试、异常信息
- [x] 4.2 补充 `fetch_feed` / `fetch_all` 的限流熔断集成测试
