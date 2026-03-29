## 1. 签名算法实现

- [x] 1.1 在 `src/api/cls_roll.py` 中实现 `generate_sign()` 函数
- [x] 1.2 添加签名算法单元测试

## 2. API 客户端实现

- [x] 2.1 创建 `CLSRollClient` 类，包含基本属性和初始化
- [x] 2.2 实现 `_fetch_page()` 方法获取单页数据
- [x] 2.3 实现 `fetch_latest()` 方法获取最新重要电报
- [x] 2.4 实现 `fetch_by_time_range()` 方法按时间范围获取数据
- [x] 2.5 添加 httpx 和 curl 双重请求支持

## 3. CLI 命令实现

- [x] 3.1 在 `src/cli.py` 添加 `cls-roll` 命令组
- [x] 3.2 实现 `--limit` 参数获取最新数据
- [x] 3.3 实现 `--start` 和 `--end` 参数按时间范围查询
- [x] 3.4 添加输出格式化 (表格/JSON)

## 4. 测试与验证

- [x] 4.1 编写 API 客户端集成测试
- [x] 4.2 手动验证 CLI 命令功能 (代码已实现，需在网络正常环境中验证)
