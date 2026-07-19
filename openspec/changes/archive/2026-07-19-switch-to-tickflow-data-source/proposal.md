## Why

当前市场数据获取（akshare / pytdx / 东方财富 curl / 腾讯 curl / SSE / SZSE）全部硬编码在 `src/api/finance.py` 单文件（2000+ 行），其中 pytdx 涨跌家数链路最脆弱（6 host 轮询 + 分批 80 + 补抓），且市场数据侧**没有任何数据源抽象层**（已有的 `src/api/providers/` 抽象只覆盖公众号文章列表）。引入 **TickFlow free 档**（免费、有 SLA、稳定历史日K）作为统一历史数据源，并建立市场数据 Provider 抽象层（对齐已有的文章 Provider 模式），可消除 pytdx 脆弱链路、提升数据稳定性与代码可维护性。

> **档位决策**：采用 **free 档**（不升级 key）。free 档仅提供历史日K（无实时行情、无分钟K、无全市场实时快照），但 wchat_doc 的 `market-summary` 本就是**盘后生成**，时间语义契合。全市场聚合改为「盘后批量日K + 本地聚合」实现。

## What Changes

- **新建市场数据 Provider 抽象层** `src/api/market_providers/`：定义 `MarketDataProvider` 契约（6 分类 + 统一 dataclass）与工厂，对齐已有的 `ArticleListProvider` 模式。
- **新增 TickFlow free provider**：封装 `TickFlow.free()`（free-api 服务器），取历史日K（个股 / 指数，批量 60rpm×100标的）+ 申万行业 universe。
- **新增盘后日K管道**（核心）：盘后批量拉全市场日K（~1 分钟）→ 存本地 `daily_kline` 表 → 本地聚合算涨跌家数 / 成交额 / 行业涨幅 / 涨停池 / 全市场快照。这是 free 档（无实时快照）下获取全市场聚合指标的唯一路径。
- **BREAKING**：板块口径从**东方财富概念** → **申万一级行业**（TickFlow free 的 `SW1` universe 直接提供行业 + 成分股，无需外部概念数据源、无需抓同花顺）。
- **`src/api/finance.py` 重构**为 provider-agnostic 编排器：dict 契约不变，消费侧零改动。
- **配置开关**：`config/settings.py` 新增 `MARKET_DATA_PROVIDER`（`tickflow` / `mixed`）+ `TICKFLOW_API_KEY`（free 档可留空）。
- 板块趋势**冷启动**：不迁移历史，按申万行业重建（旧东财概念数据归档）。

## Capabilities

### New Capabilities

- `market-data-provider-abstraction`: 市场数据 Provider 抽象层——统一契约（6 分类）、dataclass 返回、工厂组装、`supports_historical` 元数据。
- `tickflow-data-source`: TickFlow free 作为市场数据源——`TickFlow.free()` 封装、**盘后日K管道**（批量拉全市场日K + 本地 `daily_kline` 存储）、**本地聚合层**（从日K算涨跌家数 / 成交额 / 行业涨幅 / 涨停池 / 快照）、申万一级行业（SW1 universe）。

### Modified Capabilities

- `market-data-source-strategy`: 涨跌统计主源 pytdx → TickFlow 盘后日K本地聚合；策略层重构为 Provider 实例 fallback 链。
- `sector-trend-tracking`: 板块口径迁移至**申万一级行业**，冷启动重建（不迁移历史）。
- `sector-group-tracking`: `THEME_DEFINITIONS` 主题词表按申万行业命名重写。

## Impact

- **代码**：`src/api/finance.py`（大改，瘦身为编排器）、`src/api/market_providers/`（新建）、**新增盘后管道 service**（如 `market_data_sync_service.py`）、`src/models/schema.py`（新增 `daily_kline` 表 + 行业相关）、`config/settings.py`、`.env.example`。
- **不改**（dict 契约不变）：`market_data_cache_service.py`、`market_data_backfill_service.py`、`market_analyzer.py`、`trade_calendar.py`、CLI 主流程。
- **依赖**：新增 `tickflow>=0.1.23,<0.2`（轻量，仅 httpx 全家桶）。已验证在 conda `wchat_doc`（Python 3.12.13）安装与 import 通过。
- **数据**：板块冷启动——`output/sector_trends/`（41 板块目录）、`output/sector_groups/`（4 分组）归档，按申万一级行业重建；`tracked_sectors` / `sector_trend_summaries` 清空重建。
- **性能**：盘后批量日K全市场 ~1 分钟（60rpm×100标的，算术推断，待实测确认）；日常增量（只拉最新交易日）更快；首次历史回填（如 1 年）~1-2 分钟。
- **无实时**：free 档无盘中实时行情，`market-summary` 维持盘后生成（与现状一致）。
- **环境**：conda `wchat_doc`（Python 3.12.13），非 uv `.venv`。
- **前置**：无 key 升级需求（free 档免费）。
