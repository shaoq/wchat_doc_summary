## 1. 修复 CLI 执行参数透传

- [x] 1.1 修正 `market-summary` CLI 对 `trade_date` 的透传，确保指定日期真正传入市场数据收集
- [x] 1.2 修正 `market-summary` CLI 对 `force` 的透传，确保强制刷新真正作用于市场数据获取

## 2. 收敛 offline 无缓存行为

- [x] 2.1 明确并实现 `--offline` 无本地市场数据时的 CLI 提示与停止逻辑
- [x] 2.2 校验 `offline` 行为与现有规格及服务层返回语义一致

## 3. 补流程级回归测试

- [x] 3.1 增加 `market-summary` CLI 流程测试，覆盖 `--date` 与 `--force` 的调用参数传递
- [x] 3.2 增加 `--offline` 有缓存与无缓存两个场景的 CLI 行为测试
- [x] 3.3 增加 `--list` 流程测试，确认历史总结列表展示正确
- [x] 3.4 运行相关测试并确认 `market-summary` 执行行为与规格一致
