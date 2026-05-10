## 1. 采集层日志语义调整

- [x] 1.1 在 `src/api/finance.py` 中调整 pytdx 单个 host 失败日志，将可恢复尝试失败从默认 warning 降为 debug，并收集失败摘要
- [x] 1.2 在 pytdx 全部 host 耗尽且无可用统计时，输出一次最终 warning，包含 host 尝试数量和最后错误摘要
- [x] 1.3 在 `src/api/finance.py` 中调整海外市场 provider chain，主源或 fallback 单次失败仅写入 `source_attempts` 并使用 debug 级别日志
- [x] 1.4 在海外市场所有 provider 均失败时，输出一次最终 warning，包含 provider 与 failure_type 摘要

## 2. Market-summary 展示一致性

- [x] 2.1 确认 `src/cli/ai.py` 阶段 1 和预检仍以最终归一化状态展示 `ok`、`near-complete`、`partial`、`error`、`fallback`
- [x] 2.2 如现有 CLI 错误文案不足，补充最终失败状态的摘要展示，但不暴露可恢复单次尝试失败为主要结果

## 3. 测试与回归

- [x] 3.1 增加海外市场日志测试：主源 401 且 fallback 成功时不产生默认 warning，所有 provider 失败时只产生最终 warning
- [x] 3.2 增加 pytdx 日志测试：首个 host 失败但后续成功时不产生默认 warning，全部 host 失败时只产生最终 warning
- [x] 3.3 更新或补充 market-summary CLI 测试，确认 fallback/near-complete 成功路径输出不被可恢复失败日志污染
- [x] 3.4 运行相关测试：`tests/test_finance_contracts.py`、`tests/test_market_summary_cli_flow.py`、`tests/test_market_summary_logging.py`
