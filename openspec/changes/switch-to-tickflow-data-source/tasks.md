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
- [x] 6.3 SW1 行业成分映射（universes.list + get）+ 实例缓存
- [x] 6.4 涨跌幅小数口径 + 单测 → 6 passed（聚合全程小数，无 _normalize_pct 二次缩放）

## 7. TickFlow provider 组装 + finance.py 重构

- [ ] 7.1 `src/api/market_providers/tickflow/provider.py`：组装 client + 管道触发 + 本地聚合，实现 6 分类
- [ ] 7.2 `finance.py`：`SOURCE_STRATEGIES` 升级为 Provider 实例元组，adapter 调 Provider + dataclass→dict
- [ ] 7.3 `_run_source_strategy` 接入 Provider 链（逻辑不变）
- [ ] 7.4 `get_all_market_data()` dict 契约回归测试：对比重构前后输出 → verify: `pytest tests/test_finance_contract.py`

## 8. 回填扩展

- [ ] 8.1 `CATEGORY_CAPABILITIES`：TickFlow active 时 `indices` / `sectors` 标记 historical-safe（基于历史日K）
- [ ] 8.2 backfill 集成测试：历史日期回填 indices/sectors 成功 → verify: `pytest tests/test_market_data_backfill.py`

## 9. 板块口径冷启动（BREAKING，Phase 3）

- [ ] 9.1 归档旧东财概念数据：`output/sector_trends/` / `output/sector_groups/` 移至 archive，清空 `tracked_sectors` / `sector_trend_summaries`
- [ ] 9.2 按 SW1 行业重建 `tracked_sectors`（canonical_name / sector_code 用 SW1）
- [ ] 9.3 重写 `src/services/sector_group_service.py` 的 `THEME_DEFINITIONS` 按 SW1 行业命名
- [ ] 9.4 `collect_sector_evidence` SW1 口径一致性测试：`MarketSector` 与 `TrackedSector` 同口径不降级

## 10. 集成与验收

- [ ] 10.1 `wchat market-data sync` 端到端：盘后管道产出 `daily_kline` + 聚合写入 market_* 表
- [ ] 10.2 `wchat ai market-summary` 数据完整（6 分类齐全，基于本地聚合）
- [ ] 10.3 `MARKET_DATA_PROVIDER=mixed` 回滚验证：TickFlow 失败时退回 akshare/pytdx
- [ ] 10.4 现有测试套件全绿 → verify: `conda run -n wchat_doc pytest -q`
- [ ] 10.5 更新 `README.md` + `docs/`（free 档、盘后管道、申万行业板块口径）
