## 1. 涨跌统计完整性升级

- [ ] 1.1 调整 `src/api/finance.py` 的 `pytdx` 涨跌统计主路径，记录缺失样本并增加有限轮次的定向补抓
- [ ] 1.2 为涨跌统计引入 `near-complete` 质量状态，并统一返回 `ok / near-complete / partial / error` 的质量元数据
- [ ] 1.3 调整涨跌统计状态判定与相关日志/摘要逻辑，确保轻微缺失与明显不完整能被区分

## 2. 涨停股与板块 contract 扩展

- [ ] 2.1 调整 `src/api/finance.py` 的涨停股归一化逻辑，移除固定 top-20 截断，保留全量或 fullest-available 结果
- [ ] 2.2 为涨停股回退路径补充来源/质量语义，区分正式涨停池与近似候选集
- [ ] 2.3 调整板块归一化与获取逻辑，将返回规模从 `top 5 + bottom 5` 升级为 `top 10 + bottom 10`

## 3. 缓存与 market-summary 消费层同步

- [ ] 3.1 调整 `src/services/market_data_cache_service.py` 的宽度缓存门控，使 `market_statistics` 支持 `near-complete` 写入，同时继续保护已有有效缓存
- [ ] 3.2 调整 `src/cli/ai.py` 的 market-summary 阶段 1 状态展示，支持新的涨跌统计质量状态与新的板块/涨停股数量语义
- [ ] 3.3 调整 `src/services/ai_processor.py` 或相关摘要构造逻辑，使 AI 输入层在保留底层全量语义的前提下对涨停股和板块做可控展示裁剪

## 4. 测试与回归保护

- [ ] 4.1 更新 `tests/test_finance_contracts.py`，覆盖涨跌统计补抓、`near-complete` 状态、全量涨停股和 20 个板块 contract
- [ ] 4.2 更新 `tests/test_market_data_cache_service.py`，覆盖 `near-complete` 统计写缓存及 degraded 结果不覆盖有效缓存
- [ ] 4.3 更新 `tests/test_market_summary_cli_flow.py`、`tests/test_market_summary_structure.py` 及相关回归测试，覆盖新的 market-summary 输入与展示语义
