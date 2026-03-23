## 1. 依赖与环境准备

- [x] 1.1 添加 `chinese-calendar` 到 requirements.txt
- [x] 1.2 添加 `akshare` 到 requirements.txt
- [x] 1.3 创建 `templates/` 目录和 `templates/market_summary.md` 模板文件
- [x] 1.4 创建 `output/market_summaries/` 输出目录

## 2. 数据库模型

- [x] 2.1 在 `src/models/schema.py` 中添加 `MarketSummary` 模型
- [x] 2.2 运行数据库迁移创建 `market_summaries` 表

## 3. 财经数据 API

- [x] 3.1 创建 `src/api/finance.py` 模块
- [x] 3.2 实现获取 A 股指数数据的方法
- [x] 3.3 实现获取成交量数据的方法
- [x] 3.4 实现获取涨跌统计的方法
- [x] 3.5 实现获取板块数据的方法
- [x] 3.6 实现获取连板数据的方法
- [x] 3.7 添加错误处理和重试机制

## 4. 市场分析服务

- [x] 4.1 创建 `src/services/market_analyzer.py` 模块
- [x] 4.2 实现交易日判断方法 `get_latest_trade_date()`
- [x] 4.3 实现数据汇总方法 `collect_market_data()`
- [x] 4.4 实现文章筛选方法 `get_related_articles()`
- [x] 4.5 实现总结生成方法 `generate_summary()`
- [x] 4.6 实现保存方法 `save_summary()`

## 5. AI 处理器扩展

- [x] 5.1 在 `AIProcessor` 中添加 `generate_market_summary()` 方法
- [x] 5.2 创建市场总结专用的 prompt 模板
- [x] 5.3 实现模板加载逻辑

## 6. CLI 命令

- [x] 6.1 在 `src/cli.py` 中添加 `market-summary` 子命令
- [x] 6.2 实现 `--date` 参数支持
- [x] 6.3 实现 `--offline` 参数支持
- [x] 6.4 实现 `--list` 参数支持
- [x] 6.5 添加进度显示和错误提示

## 7. 测试与验证

- [x] 7.1 测试交易日判断逻辑
- [x] 7.2 测试财经数据获取
- [x] 7.3 测试市场总结生成
- [x] 7.4 测试文件和数据库保存
- [x] 7.5 测试 CLI 命令完整流程
