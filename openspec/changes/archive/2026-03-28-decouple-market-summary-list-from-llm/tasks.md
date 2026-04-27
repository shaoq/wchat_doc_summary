## 1. 调整依赖初始化顺序

- [x] 1.1 让 `market-summary --list` 分支在进入 AI 相关逻辑前完成返回
- [x] 1.2 将 `AIProcessor` 初始化延迟到真正需要 AI 生成的路径

## 2. 补回归测试

- [x] 2.1 增加无 LLM 配置下 `market-summary --list` 的测试
- [x] 2.2 运行相关测试并确认列表分支不再依赖 LLM 初始化
