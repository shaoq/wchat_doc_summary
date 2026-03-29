## 1. 全市场快照主链路修正

- [x] 1.1 调整 `src/api/finance.py` 的股票快照解析逻辑，兼容东方财富 `data.diff` 为 `list` 或 `dict`
- [x] 1.2 为全市场快照实现分页聚合与完整性校验，确保成交额和涨跌统计基于完整样本计算
- [x] 1.3 保持成交额和涨跌统计复用同一份快照，避免重复抓取

## 2. 宽度数据质量状态

- [x] 2.1 为成交额和涨跌统计设计并输出结构化质量状态，至少覆盖 `ok / partial / error`
- [x] 2.2 在主快照不完整或失效时，先尝试备用源，再返回带降级状态的零值 contract
- [x] 2.3 更新市场数据聚合结果结构，使 CLI 和缓存层可读取宽度数据状态与样本规模信息

## 3. CLI 与缓存保护

- [x] 3.1 调整 `src/cli/ai.py` 的状态渲染逻辑，仅在宽度数据状态为 `ok` 时显示”已获取”
- [x] 3.2 为 `partial` 和 `error` 宽度数据提供明确的用户提示，避免 `0亿` 和 `0/0/0` 被误报为成功
- [x] 3.3 调整 `src/services/market_data_cache_service.py`，仅对 `ok` 的成交额和涨跌统计执行写库或覆盖

## 4. 测试与回归保护

- [x] 4.1 更新 `tests/test_finance_contracts.py`，覆盖 `diff=dict`、分页聚合、部分样本和降级状态
- [x] 4.2 更新 `tests/test_market_summary_cli_flow.py`，校验宽度数据在 `ok / partial / error` 下的 CLI 展示语义
- [x] 4.3 更新 `tests/test_market_data_cache_service.py` 和相关实时取数测试，校验无效宽度数据不会污染缓存
