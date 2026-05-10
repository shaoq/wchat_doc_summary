## 1. 海外市场上下文 contract 与采集编排

- [x] 1.1 定义 `global_market_context` 的标准化数据结构、状态枚举以及 `target_a_trade_date / captured_at / as_of / session` 字段语义
- [x] 1.2 在 `src/services/market_analyzer.py` 中增加海外市场上下文采集编排，并接入当前交易日在线模式的获取流程
- [x] 1.3 在 `src/api/finance.py` 或新增专用服务中实现第一期美股/风险指标信号采集与归一化，支持 `ok / partial / error` 状态输出

## 2. 缓存与历史回放

- [x] 2.1 扩展 `src/services/market_data_cache_service.py`，支持按目标 A 股交易日保存海外市场上下文及其抓取元数据
- [x] 2.2 调整缓存读取 contract，使在线路径与缓存回放路径返回同结构的 `global_market_context`
- [x] 2.3 明确历史交易日和 `--offline` 路径的行为：只读取本地缓存，不对缺失海外上下文做在线补抓

## 3. CLI 与 AI 输入集成

- [x] 3.1 调整 `src/cli/ai.py` 的 market-summary 第 1 阶段展示，输出海外市场上下文状态、`session`、`as_of` 和关键摘要
- [x] 3.2 扩展 `src/services/ai_processor.py` 的 `generate_market_summary()` 输入和模板占位，按独立证据组注入海外市场上下文
- [x] 3.3 调整 prompt 数据缺口表达，确保海外上下文缺失或部分缺失时模型不会把未知信号当作事实

## 4. 测试与回归保护

- [x] 4.1 新增或更新财经数据 contract 测试，覆盖海外市场上下文的字段结构、状态语义和时间字段
- [x] 4.2 更新 `tests/test_market_data_cache_service.py`，覆盖海外上下文缓存写入、读取、缺失和历史回放场景
- [x] 4.3 更新 `tests/test_market_summary_cli_flow.py`、`tests/test_market_summary_structure.py` 及相关回归测试，覆盖 CLI 展示、离线/历史行为和 prompt 输入语义
