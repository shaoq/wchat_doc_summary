## 1. CLS 自动补抓 contract

- [x] 1.1 扩展 `src/services/cls_telegraph_service.py` 和 `src/services/cls_watch_service.py` 的抓取结果表达能力，支持区分自动补抓的 `ok / empty / error` 结果
- [x] 1.2 在 `src/services/market_analyzer.py` 中实现在线模式下的“本地优先、查空自动补抓、补抓后回查”逻辑，分别覆盖电报和看盘窗口

## 2. CLI 状态展示

- [x] 2.1 调整 `src/cli/ai.py` 的新闻阶段和生成前预检展示，使 CLS 来源能体现自动补抓后的最终状态与过程摘要
- [x] 2.2 保持 `--offline` 模式只读本地，不触发任何 CLS 自动补抓，并为该路径补充明确回归保护

## 3. 测试与回归保护

- [x] 3.1 更新 `tests/test_news_ingestion.py` 或相关测试，覆盖在线命中本地、自动补抓成功、自动补抓后为空、自动补抓失败、离线跳过补抓等场景
- [x] 3.2 更新 `tests/test_market_summary_cli_flow.py`，覆盖阶段 2 与预检输出中的 CLS 自动补抓结果展示
