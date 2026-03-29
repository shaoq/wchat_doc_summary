## Why

`market-summary` 的成交额和涨跌统计虽然已经具备 `ok / partial / error` 质量状态，但当前东方财富全市场快照分页策略仍然会稳定停在不完整样本。

在 2026-03-29 的实际探测中，东方财富股票快照接口对 `page=1,pz=5000` 和 `page=2,pz=5000` 都返回：

- `total=5518`
- `diff` 实际仅 100 条
- `diff` 结构为 `dict`

现有实现按 `page <= 20` 固定上限分页，因此最多累积 `20 * 100 = 2000` 条记录，最终持续触发：

- `成交额: 样本不完整 (2000/5518)`
- `涨跌统计: 样本不完整 (2000/5518)`

这说明之前的“分页聚合”修复仍保留了错误假设：代码相信 `pz=5000` 会生效，但上游实际强制按约 100 条分页。继续维持该实现会让宽度数据长期停留在可诊断但不可用的 partial 状态，无法恢复到稳定成功路径。

## What Changes

- 将全市场快照分页策略改为基于“首页实际返回条数”和上游 `total` 的自适应分页，而不是固定 20 页。
- 为分页聚合增加按股票代码去重与更稳健的终止条件，避免页间重复或空页导致的伪完整判断。
- 仅在真正尝试完所需分页后再判定 `ok / partial`，让成交额和涨跌统计尽可能恢复到完整样本计算。
- 补充针对“`pz=5000` 失效、实际上游每页只回 100 条”的回归测试，防止问题再次出现。

## Capabilities

### Modified Capabilities

- `market-data-source-strategy`: 调整全市场快照的分页策略与完整性判定逻辑，使共享快照链路能适配上游实际分页行为，而不是停在固定 2000 条样本。

## Impact

- 受影响代码:
  - `src/api/finance.py`
- 受影响测试:
  - `tests/test_finance_contracts.py`
  - `tests/test_harden_realtime.py`
  - 视实现情况可能补充 `tests/test_market_summary_cli_flow.py`
- 受影响行为:
  - `wchat ai market-summary`
  - 宽度数据质量状态 `ok / partial / error` 的触发比例与准确性
