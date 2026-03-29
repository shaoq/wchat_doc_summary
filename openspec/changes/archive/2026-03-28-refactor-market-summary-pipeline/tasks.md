## 1. 修复显式错误与收敛主流程入口

- [x] 1.1 修复 `wchat ai market-summary --list` 中历史记录时间字段错误,恢复历史总结列表展示
- [x] 1.2 将 `market-summary` 生成流程中的财联社重要电报显式传入 `AIProcessor.generate_market_summary()`
- [x] 1.3 清理 `market-summary` CLI 中与流程编排无关的散乱逻辑，为后续服务层收敛做准备

## 2. 统一市场数据结构与缓存行为

- [x] 2.1 定义 `market-summary` 使用的统一 `market_data` 结构，并统一指数字段为 `name / close / change`
- [x] 2.2 调整 `MarketDataCacheService` 的读写与格式化逻辑，使缓存返回结构与在线返回结构完全一致
- [x] 2.3 将 `MarketAnalyzer.collect_market_data()` 切换为缓存优先策略，覆盖历史日期、当日交易中、当日收盘后和 `--force` 分支
- [x] 2.4 重定义 `--offline` 行为为仅使用本地可用市场数据，并补充缓存缺失时的明确提示

## 3. 接入新闻聚合与交易日相关文章窗口

- [x] 3.1 为 `market-summary` 新增统一的新闻聚合步骤，分别收集 CLS telegraphs、CLS watch 和相关市场文章
- [x] 3.2 将财联社看盘数据正式接入 `market-summary` 主流程，并保证单一新闻源缺失时仍可继续生成总结
- [x] 3.3 调整 `AIProcessor.generate_market_summary()` 与模板输入，保持新闻来源边界清晰且不依赖抓取层原始格式
- [x] 3.4 将 `get_related_articles()` 从固定回溯天数改为交易日感知的文章时间窗口
- [x] 3.5 在 `market-summary` CLI 输出中展示实际使用的文章时间窗口与数据来源摘要

## 4. 补齐验证与回归测试

- [x] 4.1 更新并扩展 `market_data` 相关单元测试，覆盖缓存命中、缓存缺失、force refresh 和结构一致性
- [x] 4.2 为 `market-summary` CLI 补充流程测试，覆盖 `--list`、`--offline`、`--force` 和指定 `--date`
- [x] 4.3 为市场新闻聚合与 prompt 组装补充测试，验证 telegraph/watch/article 三类输入的兼容性
- [x] 4.4 运行回归测试并验证 `output/market_summaries` 的生成结果满足新的数据链路要求
