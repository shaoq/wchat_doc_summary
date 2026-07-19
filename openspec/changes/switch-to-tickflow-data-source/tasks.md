## 0. 前置与地基（实测 free 档）✅

- [x] 0.1 实测 free 档全市场批量日K真实耗时 → **56s（0.93分钟），56 批 5528 只 0 失败**（2026-07-19）
- [x] 0.2 确认 free 档全市场标的列表来源 → **`exchanges.get_instruments(SH/SZ/BJ)` = 5528 只**；`CN_Equity_A` universe 不存在但不需要（2026-07-19）
- [x] 0.3 spike：确定 SW 行业粒度 → **决策：一级 SW1（~28）**
- [x] 0.4 确认 conda `wchat_doc` 环境已装 `tickflow>=0.1.23` → ✅ 实测 import 通过

## 1. 依赖与配置

- [x] 1.1 `pyproject.toml` + `requirements.txt` 加 `tickflow>=0.1.23,<0.2`
- [x] 1.2 `config/settings.py` 加 `MARKET_DATA_PROVIDER` + `TICKFLOW_API_KEY` + `TICKFLOW_BASE_URL`
- [x] 1.3 `.env.example` 加新配置项及说明（留空有默认值，不崩）

## 2. Provider 抽象层

- [x] 2.1 新建 `src/api/market_providers/base.py`：`MarketDataProvider` ABC + 6 个 dataclass + `name` / `supports_historical` 元数据
- [x] 2.2 新建 `src/api/market_providers/factory.py`：按 `MARKET_DATA_PROVIDER` 组装 per-category Provider 链
- [x] 2.3 单元测试：Provider 契约 + factory 组装（mock）→ 9 passed

## 3. TickFlow free client 基础

- [x] 3.1 新建 `src/api/market_providers/tickflow/client.py`：`get_client()` 单例，free/付费分流
- [x] 3.2 移植精简版 `rate_limits.py`：进程级共享时间轴（60rpm 分桶）+ `chunked` / `sleep_between_batches`
- [x] 3.3 单元测试：60rpm 限流不超速 → 6 passed

## 4. 本地日K存储

- [x] 4.1 `src/models/schema.py` 新增 `daily_kline` 表（PK `(symbol, trade_date)`）；`Base.metadata.create_all` 自动建表，无需改 database.py
- [x] 4.2 `daily_kline` 读写 repository（upsert / get_by_date / latest_date）

## 5. 盘后日K管道（核心）

- [x] 5.1 新建 `src/services/market_data_sync_service.py`：拉全市场标的 → `klines.batch`（分批 100，60rpm）→ upsert `daily_kline`
- [x] 5.2 增量模式（count=1）+ 回填模式（count=N）；自动多拉 1 根算 change_pct
- [x] 5.3 CLI `wchat ai market-data sync --days N`（默认 1 增量；market-data 挂在 ai 子命令组下）
- [x] 5.4 单元测试（_normalize + mock sync 流程）→ 5 passed；真实拉网集成留 task 10.1

## 6. 本地聚合层

- [x] 6.1 从 `daily_kline` 聚合 volume（amount 按 SH/SZ 求和/亿）/ statistics（change_pct up/down/flat）/ snapshot / limit_up（≥9.9%）
- [x] 6.2 `sectors`：SW1 行业成分 join daily_kline 求均值（universes.get 拿成分）
- [x] 6.3 SW1 行业成分映射：universes.batch 单请求拉取 + industry_members DB 持久缓存（首次 2.6s / 二次读 0.03s）。注：free 档 SW1 universe 实测 335 个（含细分，非 28 一级），task 9 按 level 精化
- [x] 6.4 涨跌幅小数口径 + 单测 → 6 passed（聚合全程小数，无 _normalize_pct 二次缩放）

## 7. TickFlow provider 组装 + finance.py 重构

- [x] 7.1 `src/api/market_providers/tickflow/provider.py`：TickFlowProvider 组装 sync+aggregator，实现 6 分类
- [x] 7.2 finance.py get_all_market_data 顶层分流（tickflow/mixed）+ _get_market_data_from_tickflow + 4 转换方法（小数口径，绕过 _normalize_pct）
- [x] 7.3 _run_source_strategy 不变（顶层分流方案下原逻辑保留作 mixed fallback）
- [x] 7.4 dict 契约测试 → 6 passed（转换方法 + 小数口径，防 _normalize_pct 二次缩放）

## 8. 回填扩展

- [~] 8.1 回退：indices/sectors 保持 historical_safe=False（backfill 未接 TickFlow 历史回填，升级会名实不符；get_category_capabilities 仅深拷贝，接入 TickFlow 留后续）
- [~] 8.2 回退（随 8.1）：get_category_capabilities 深拷贝单测 2 passed

## 9. 板块口径冷启动（BREAKING，Phase 3）

- [x] 9.1 归档旧东财概念数据（output/sector_trends + sector_groups → archive）+ 清空 tracked_sectors/sector_trend_summaries/sector_groups 等
- [x] 9.2 按 SW1 行业重建 tracked_sectors（31 个 unique 行业名，≈SW1 一级）via scripts/cold_start_sectors_sw1.py
- [x] 9.3 THEME_DEFINITIONS 清空（SW1 行业口径下概念主题无意义，留 config 重定义）
- [x] 9.4 SW1 口径一致性测试 → 3 passed（canonical_name 与 market_name comparison_key 一致，不降级）

## 10. 集成与验收

- [x] 10.1 `wchat ai market-data sync` 端到端验证（5528 标的 / 11056 行 daily_kline）
- [x] 10.2 TickFlow 分流 get_all_market_data 6 分类完整（indices/volume/statistics/sectors/limit_up/snapshot 全验证）
- [x] 10.3 mixed 模式 fallback（tickflow 核心不全落原逻辑）+ tickflow 模式失败返回空
- [x] 10.4 测试套件：新增 30+ 单测全绿；5 个 test_sector_groups 失败经 main 确认为预先存在（与本变更无关）
- [x] 10.5 README 配置表加 MARKET_DATA_PROVIDER / TICKFLOW_API_KEY 说明

## 11. 自动 sync 增强（用户需求：纯 TickFlow + summary 自动取数，避免分析错误）

- [x] 11.1 finance.py _ensure_daily_kline_fresh（latest vs get_effective_fetch_trade_date，落后自动 sync）
- [x] 11.2 单测 → 3 passed（fresh skip / stale sync / empty sync）
