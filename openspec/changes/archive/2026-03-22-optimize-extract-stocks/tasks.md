## 1. 并发控制

- [x] 1.1 在 `AIProcessor.batch_extract_stocks` 中添加 `asyncio.Semaphore(3)` 限制并发
- [x] 1.2 验证并发控制生效，不再出现连接池耗尽错误

## 2. 默认输出

- [x] 2.1 修改 `extract_stocks` 命令，添加默认输出路径逻辑
- [x] 2.2 创建 `output/extract_stocks/` 目录（如果不存在）
- [x] 2.3 验证默认输出文件格式正确：`{mp_id}_stocks_{YYMMDD}.txt`
