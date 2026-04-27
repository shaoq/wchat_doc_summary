## 1. 涨跌统计 fallback 收缩

- [x] 1.1 调整 `src/api/finance.py` 的涨跌统计获取逻辑，移除 `_get_statistics_from_spot_em()` 的 fallback 调用
- [x] 1.2 保持 `pytdx` 的 `ok / partial / error` 质量状态 contract，并将 `partial` 与 `error` 直接作为最终统计结果语义

## 2. CLI 来源语义收口

- [x] 2.1 调整 `src/cli/ai.py` 的宽度来源标签逻辑，移除涨跌统计 AKShare fallback 相关文案分支
- [x] 2.2 校验阶段 1 输出在 `pytdx ok / partial / error` 下仍然可读，但不再暗示存在 statistics 的旧链路兜底

## 3. 测试与回归保护

- [x] 3.1 更新 `tests/test_finance_contracts.py`，删除或改写“statistics fallback uses akshare”假设，改为验证不再尝试旧链路
- [x] 3.2 更新 `tests/test_market_summary_cli_flow.py`，删除或改写“涨跌统计旧链路兜底”相关来源标签断言
