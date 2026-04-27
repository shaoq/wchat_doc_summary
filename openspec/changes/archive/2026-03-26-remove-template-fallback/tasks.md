## 1. 移除 CLI 降级逻辑

- [x] 1.1 移除 `cli.py` 中 `market-summary` 命令的 try/except 降级分支
- [x] 1.2 移除 `ai_failed` 变量及相关条件输出逻辑

## 2. 移除 market_analyzer 冗余方法

- [x] 2.1 移除 `market_analyzer.py` 中的 `generate_summary()` 方法
- [x] 2.2 移除 `market_analyzer.py` 中的 `_load_template()` 方法

## 3. 验证

- [x] 3.1 运行 `python src/cli.py ai market-summary --force` 验证正常流程
- [x] 3.2 验证 AI 失败时正确抛出错误（可模拟 API 错误）
