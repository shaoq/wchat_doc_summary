## Why

用户需要自动化 A 股市场每日总结功能，结合已订阅的财经公众号文章和网络行情数据，生成结构化的市场分析报告。当前系统只能抓取和存储文章，缺少智能化的市场分析和总结能力。

## What Changes

- 新增 `wchat ai market-summary` 命令，自动生成 A 股交易日市场总结
- 新增交易日判断逻辑（排除周末和节假日）
- 新增财经数据 API 集成（获取指数、板块、个股数据）
- 新增市场总结模板文件（用户可编辑）
- 新增数据库表存储历史总结记录
- 输出同时保存到数据库和 Markdown 文件

## Capabilities

### New Capabilities

- `market-summary`: A 股市场交易日自动总结功能，包括：
  - 交易日智能判断（周末 + 节假日）
  - 多数据源整合（已抓取文章 + 网络行情）
  - 结构化报告生成（按模板格式）
  - 历史记录存储与查询

- `finance-data`: 财经数据获取能力，包括：
  - A 股指数数据（上证、深证、创业板）
  - 板块涨跌数据
  - 个股连板统计
  - 龙头个股追踪

### Modified Capabilities

- `ai-processor`: 扩展 AI 处理能力，支持市场总结生成

## Impact

- **新增文件**:
  - `templates/market_summary.md` - 市场总结模板
  - `src/services/market_analyzer.py` - 市场分析服务
  - `src/api/finance.py` - 财经数据 API 客户端
  - `output/market_summaries/` - 输出目录

- **修改文件**:
  - `src/cli.py` - 添加 `market-summary` 命令
  - `src/models/schema.py` - 添加 `MarketSummary` 模型
  - `requirements.txt` - 添加 `chinese-calendar`, `akshare` 依赖

- **新增依赖**:
  - `chinese-calendar` - 中国节假日判断
  - `akshare` - 开源财经数据接口
