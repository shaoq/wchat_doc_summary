## Why

`market-summary` 目前主要围绕最近一个交易日的 A 股盘面、财联社资料和相关文章生成总结，但缺少对当晚美股与全球风险偏好的结构化观测。实际使用中，次交易日 A 股的开盘预期经常受到美股指数、波动率、美元与美债收益率等隔夜信号影响，仅依赖零散新闻很难稳定还原这部分传导关系。

现在需要把这类“隔夜海外市场上下文”纳入 `market-summary` 的正式输入 contract，使系统在盘后和次日盘前生成总结时，能够更一致地解释 A 股情绪延续、风格切换和风险偏好变化。

## What Changes

- 为 `market-summary` 增加结构化的海外市场上下文输入，重点覆盖美股三大指数、风险偏好指标和少量关键资产/龙头代理信号。
- 明确海外市场上下文的时间语义，区分 `target_a_trade_date`、实际抓取时间 `captured_at`、行情时间 `as_of` 与美股交易阶段 `session`，避免把隔夜数据误当成 A 股同日盘内数据。
- 为在线模式补充海外市场数据采集链路，并定义成功、部分成功、失败时的标准化状态表达。
- 扩展 `market-summary` CLI 阶段输出与 AI prompt 输入，使用户和模型都能看到海外市场上下文的来源、时间与质量状态。
- 扩展缓存与历史回放语义，使历史交易日总结在可用时能够读取已保存的海外市场上下文，而不是临时依赖实时抓取。
- 补充回归测试，覆盖时间窗口、缓存、CLI 展示、prompt 结构和退化路径。

## Capabilities

### New Capabilities
- `global-market-context`: 为 A 股总结提供与目标交易日关联的海外市场上下文采集、标准化、时间语义与状态表达能力。

### Modified Capabilities
- `market-summary`: 市场总结的输入 contract、CLI 展示和 AI 证据分组将扩展为显式包含海外市场上下文。
- `market-data-cache`: 市场总结相关缓存将支持保存和回放与目标 A 股交易日绑定的海外市场上下文。

## Impact

- 受影响代码：
  - `src/services/market_analyzer.py`
  - `src/services/ai_processor.py`
  - `src/cli/ai.py`
  - `src/services/market_data_cache_service.py`
  - `src/api/finance.py`
  - 可能新增海外市场数据采集服务或在现有财经客户端内扩展采集能力
  - `templates/market_summary.md`
- 受影响测试：
  - `tests/test_market_summary_cli_flow.py`
  - `tests/test_market_summary_structure.py`
  - `tests/test_market_data_cache_service.py`
  - 与财经数据 contract、交易日时间窗口和 prompt 结构相关的回归测试
- 受影响数据与 contract：
  - `market_data`/总结输入结构将新增海外市场上下文字段
  - `market-summary` 阶段 1 的状态展示将新增海外市场信息
  - 历史回放与缓存记录需要区分 A 股目标交易日和海外市场实际抓取时间
