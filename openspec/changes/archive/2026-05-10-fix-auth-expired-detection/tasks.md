## 1. 修改 Token 失效检测

- [x] 1.1 修改 `src/api/weread.py` `_request()` 中 Token 失效检测：移除 `status_code == 401` 条件，仅保留 `"WeReadError401" in e.response.text` 判断

## 2. 测试

- [x] 2.1 添加测试用例：验证 HTTP 500 + `WeReadError401` 抛出 `AuthExpiredError`
- [x] 2.2 添加测试用例：验证 HTTP 401 + `WeReadError401` 仍然抛出 `AuthExpiredError`
- [x] 2.3 运行全部测试确认无回归
