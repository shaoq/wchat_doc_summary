## 1. 依赖与宽度适配器准备

- [x] 1.1 在 `requirements.txt` 中引入 `mootdx`，并补充必要的依赖说明或初始化约束
- [x] 1.2 在 `src/api/finance.py` 中增加 `mootdx` 宽度样本适配器，能够返回用于成交额和涨跌统计的统一全市场样本
- [x] 1.3 为 `mootdx` 宽度样本适配器补充最小 contract 测试，验证样本可被现有聚合逻辑消费

## 2. 宽度数据主链路切换

- [x] 2.1 调整 `FinanceClient` 的宽度数据 source strategy，使成交额和涨跌统计优先走 `mootdx`
- [x] 2.2 保持成交额和涨跌统计复用同一轮 `mootdx` 样本，避免拆成两个独立请求
- [x] 2.3 将现有东方财富/AKShare 宽度链路降为次级兜底，并保留失败时的零值 contract
- [x] 2.4 更新 `breadth_quality` 或等价来源标识，使调用方能识别 primary / fallback / error 三类结果

## 3. CLI 与缓存行为对齐

- [x] 3.1 调整 `src/cli/ai.py` 的 stage 1 来源与状态展示，使宽度数据能体现免费主源命中或兜底结果
- [x] 3.2 验证 `src/services/market_analyzer.py` 无需破坏现有 contract 即可透传新的宽度来源语义
- [x] 3.3 校验 `src/services/market_data_cache_service.py` 在新来源语义下仍只缓存有效宽度数据

## 4. 回归验证

- [x] 4.1 更新 `tests/test_finance_contracts.py`，覆盖 `mootdx` 主源成功、旧链路兜底和完全失败三条路径
- [x] 4.2 更新 `tests/test_market_summary_cli_flow.py`，校验 stage 1 对免费主源、兜底和降级的展示语义
- [x] 4.3 更新 `tests/test_market_data_cache_service.py` 与相关实时取数测试，确认缓存门控与来源标识兼容
