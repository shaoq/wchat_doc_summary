## Why

`market-summary` 现在已经能生成可读的市场总结，但“后续策略建议”仍然不稳定：有时缺失、有时混在其他章节里，而且经常基于不完整数据给出偏泛或偏主观的判断。继续在这种弱约束模板上迭代，会让总结内容看起来像分析报告，但缺少可复盘、可验证、可降级的输出标准。

## What Changes

- 为 `market-summary` 明确更稳定的总结结构，单独定义“明日观察”和“后续策略建议 / 风险提示”章节。
- 收紧市场总结中策略建议的生成规则，要求建议绑定当日数据与消息依据，而不是泛化陈述。
- 明确数据不足场景下的降级语义：当关键行情或题材证据缺失时，输出观察项与风险提示，而不是强方向性建议。
- 调整市场总结模板与 AI 输入组织方式，使板块、个股、新闻催化和风险线索更容易被模型稳定消费。
- 补充针对市场总结内容结构与降级行为的测试，避免模板和提示词回归漂移。

## Capabilities

### New Capabilities

### Modified Capabilities
- `market-summary`: 调整市场总结的输出结构与内容要求，明确策略建议、观察清单和风险提示的稳定章节与降级语义。
- `ai-processing`: 调整 AI 生成市场总结时的提示约束与输入组织方式，确保策略建议基于显式证据生成。

## Impact

- **Affected code**:
  - `templates/market_summary.md`
  - `src/services/ai_processor.py`
  - 可能需要补充少量市场总结输入整理辅助逻辑
- **Affected tests**:
  - 需要新增或扩展市场总结内容生成相关测试
  - 可能扩展 `tests/test_market_summary_cli_flow.py`
- **Affected behaviors**:
  - `wchat ai market-summary`
  - 市场总结正文结构
  - 数据不足时的策略建议与风险提示输出
