## 1. 多源抓取与失败分类

- [x] 1.1 在 `src/api/finance.py` 中为海外市场上下文定义 provider 尝试结果结构、`failure_type` 枚举和有序 fallback 编排
- [x] 1.2 为当前主源 Yahoo 401、空返回、网络失败等情况补充标准化错误分类与消息生成
- [x] 1.3 接入至少一个可替代 provider，并把最终 `source`、`source_attempts`、`degraded` 元数据并入标准化 `global_market_context`

## 2. 缓存保护与回放

- [x] 2.1 调整 `src/services/market_data_cache_service.py` 的海外市场上下文保存逻辑，避免 `error` 覆盖已有 `ok/partial` 缓存
- [x] 2.2 更新 `src/services/market_analyzer.py` 的在线抓取与缓存回放编排，使 fallback 元数据在实时和缓存路径返回同结构

## 3. CLI 与 AI 集成

- [x] 3.1 调整 `src/cli/ai.py` 的阶段 1 海外市场展示，体现主源失败后 fallback 命中或全部失败的状态
- [x] 3.2 调整 `src/services/ai_processor.py` 与 `templates/market_summary.md`，将结构化失败类型纳入缺口提示并禁止模型补全未知海外信号

## 4. 测试与回归

- [x] 4.1 更新 `tests/test_finance_contracts.py`，覆盖 provider fallback、401 分类和来源元数据 contract
- [x] 4.2 更新 `tests/test_market_data_cache_service.py`，覆盖质量优先缓存保护和 provenance 回放
- [x] 4.3 更新 `tests/test_market_summary_cli_flow.py` 与 `tests/test_market_summary_structure.py`，覆盖 fallback 展示与 prompt 缺口约束
