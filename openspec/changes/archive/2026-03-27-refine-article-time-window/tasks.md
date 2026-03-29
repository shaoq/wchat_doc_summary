## 1. MarketAnalyzer 方法实现

- [x] 1.1 添加 `get_next_trade_date(date)` 方法到 `src/services/market_analyzer.py`
- [x] 1.2 添加 `get_article_time_window(trade_date)` 方法到 `src/services/market_analyzer.py`
- [x] 1.3 修改 `get_related_articles(trade_date)` 方法，使用精确时间窗口查询

## 2. CLI 输出修改

- [x] 2.1 修改 `_format_articles_summary` 函数添加时间窗口参数
- [x] 2.2 修改 CLI 中获取文章部分，打印时间窗口信息

## 3. 测试

- [ ] 3.1 为 `get_next_trade_date` 方法编写单元测试
- [ ] 3.2 为 `get_article_time_window` 方法编写单元测试
- [ ] 3.3 验证 CLI 输出正确显示时间窗口

## 4. 验证

- [ ] 4.1 运行现有测试确保无回归
- [ ] 4.2 手动测试周五、节假日等边界场景
