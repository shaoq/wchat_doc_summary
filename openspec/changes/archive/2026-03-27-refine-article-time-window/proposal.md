## Why

市场总结功能在获取公众号文章时，当前使用简单的"往前 N 天"时间范围，没有考虑交易日的精确时间窗口。这导致：
1. 包含了不属于该交易日的文章（如盘前发布的隔夜分析）
2. 遗漏了收盘后发布的重要盘后分析文章
3. 在节假日后第一个交易日，可能包含过多非交易日文章

需要改为：交易日收盘后 15:00 到下一交易日开盘前 9:15 之间的精确时间窗口，并正确处理节假日。

## What Changes

- 新增 `get_next_trade_date(date)` 方法：获取指定日期之后的下一个交易日
- 新增 `get_article_time_window(trade_date)` 方法：返回精确的文章筛选时间窗口
- 修改 `get_related_articles(trade_date)` 方法：使用精确时间窗口替代 days_back 参数
- 修改 CLI `market_summary` 命令：在获取文章时打印时间窗口信息

## Capabilities

### New Capabilities

- `trading-time-window`: 基于交易日的精确时间窗口计算，用于筛选与特定交易日相关的公众号文章

### Modified Capabilities

- `market-summary`: 修改文章获取逻辑，使用交易日时间窗口替代简单的天数回溯

## Impact

| 文件 | 影响 |
|------|------|
| `src/services/market_analyzer.py` | 新增 2 个方法，修改 `get_related_articles()` |
| `src/cli.py` | 添加时间窗口打印输出 |
| `openspec/specs/market-summary/spec.md` | 更新规格说明 |
