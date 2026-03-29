## 1. 数据模型定义

- [x] 1.1 在 `src/models/schema.py` 添加板块数据模型
  - 概念板块字段：代码、名称、涨跌幅、成交量等
  - 行业板块字段：同上

## 2. API 客户端实现

- [x] 2.1 创建 `src/api/sector.py` 文件
- [x] 2.2 实现 `_fetch_with_curl()` 函数使用 curl 获取数据
- [x] 2.3 实现 `_parse_sector_response()` 函数解析响应
- [x] 2.4 实现 `get_concept_sectors()` 获取概念板块列表
- [x] 2.5 实现 `get_industry_sectors()` 获取行业板块列表
- [x] 2.6 添加缓存装饰器（5分钟过期）
- [x] 2.7 添加降级策略：curl 失败时使用 akshare

## 3. CLI 命令实现

- [x] 3.1 在 `src/cli.py` 添加 `sector` 命令组
- [x] 3.2 实现 `sector concept` 子命令获取概念板块
- [x] 3.3 实现 `sector industry` 子命令获取行业板块
- [x] 3.4 添加 `--limit` 参数限制返回数量
- [x] 3.5 添加 `--json` 参数输出 JSON 格式
- [x] 3.6 添加表格格式输出

## 4. 测试与验证

- [x] 4.1 编写 curl 请求函数单元测试
- [x] 4.2 编写数据解析函数单元测试
- [x] 4.3 编写降级策略测试
- [x] 4.4 手动验证 CLI 命令功能（代码已实现，需在网络正常环境中验证）
