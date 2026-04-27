## 1. 依赖与适配器准备

- [x] 1.1 在 `requirements.txt` 和 `pyproject.toml` 中引入 `pytdx`，并移除或降级 `mootdx` 的宽度主路径依赖说明
- [x] 1.2 在 `src/api/finance.py` 中新增交易所官方成交额解析器，能够分别获取并归一化上交所与深交所成交额
- [x] 1.3 在 `src/api/finance.py` 中新增 `pytdx` A 股 universe 与 quotes 聚合逻辑，能够输出稳定的涨跌统计样本

## 2. 宽度数据主链路切换

- [x] 2.1 将成交额主路径切换为“官方成交额 -> 旧链路兜底”
- [x] 2.2 将涨跌统计主路径切换为“pytdx -> 旧链路兜底”
- [x] 2.3 更新 `breadth_quality` 或等价来源标识，使成交额与涨跌统计可分别表达 official / pytdx / fallback / error
- [x] 2.4 将 `mootdx` 从宽度主路径中移除，避免继续作为默认成功路径参与阶段 1

## 3. CLI 与缓存对齐

- [x] 3.1 调整 `src/cli/ai.py` 的阶段 1 文案，使宽度来源能够表达“官方成交额 + pytdx 统计”的组合成功
- [x] 3.2 验证 `src/services/market_analyzer.py` 无需破坏现有 contract 即可透传新的宽度来源语义
- [x] 3.3 校验 `src/services/market_data_cache_service.py` 在新来源语义下仍只缓存有效宽度数据

## 4. 测试与回归验证

- [x] 4.1 更新 `tests/test_finance_contracts.py`，覆盖官方成交额成功、`pytdx` 统计成功、旧链路兜底和完全失败路径
- [x] 4.2 更新 `tests/test_market_summary_cli_flow.py`，校验阶段 1 对 official / pytdx / fallback / error 的展示语义
- [x] 4.3 更新 `tests/test_market_data_cache_service.py` 与相关实时取数测试，确认缓存门控与新的来源标识兼容
