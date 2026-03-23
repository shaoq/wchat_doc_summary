## 1. 实现 upsert 逻辑

- [x] 1.1 修改 `MarketAnalyzer.save_summary()` 方法，添加 upsert 逻辑
  - 先调用 `get_existing_summary()` 查询是否存在
  - 存在时更新 `content` 和 `data_sources`
  - 不存在时插入新记录

## 2. 验证

- [x] 2.1 测试首次保存（插入）
- [x] 2.2 测试重复保存（更新）
- [x] 2.3 测试 `--force` 重复执行命令
