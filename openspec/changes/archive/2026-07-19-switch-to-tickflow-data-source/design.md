## Context

当前市场数据获取的现状与约束（基于 `src/api/finance.py` 精读）：

- **数据源硬编码单点集中**：akshare / pytdx / 东方财富 curl / 腾讯 curl / SSE / SZSE 全部调用集中在 `src/api/finance.py`（2000+ 行）。pytdx 涨跌家数链路最脆弱（6 host 轮询 + 分批 80 + 补抓）。
- **无市场数据 Provider 抽象**：`SOURCE_STRATEGIES` 只是"数据源名字元组"，每个名字绑死在 `FinanceClient` 私有方法。已有的 `src/api/providers/`（`ArticleListProvider` ABC + factory）只覆盖公众号文章。
- **消费侧只认 dict 契约**：`market_data_cache_service` / `market_data_backfill_service` / `market_analyzer` / CLI 全部依赖 `get_all_market_data()` 返回的 dict，不直接碰数据源——重构最大利好。
- **已有 fallback 编排器**：`_run_source_strategy` 已是 provider-agnostic，可直接复用。

**TickFlow free 档实测结果**（`TickFlow.free()`，free-api 服务器）：

| 能力 | free 档 | 备注 |
|------|---------|------|
| `klines.get` 日K（单只/指数） | ✅ 秒级 | 个股 / 指数历史日K |
| `klines.batch` 日K（批量） | ✅ 60rpm×100标的 | 全市场 ~1 分钟（算术推断） |
| `universes.list` | ✅ 1013 个 universe | **全为申万行业 SW1/SW2/SW3**，无概念 |
| `quotes.get_by_universes` 全市场快照 | ❌ 免费不支持实时 | **关键约束** |
| `quotes.get` 实时行情 | ❌ 不支持 | free 档无实时 |

**核心约束**：free 档**没有全市场实时快照**，所有"全市场聚合"指标（涨跌家数 / 成交额 / 行业涨幅 / 涨停池 / 快照）只能靠「盘后批量日K + 本地聚合」实现。

## Goals / Non-Goals

**Goals:**

- 建立市场数据 Provider 抽象层，数据源可配置、可替换、可并存。
- TickFlow free 作为主力历史数据源，消除 pytdx 涨跌家数脆弱链路。
- **盘后日K管道 + 本地聚合**：free 档无实时快照的唯一可行路径。
- 板块口径切到申万一级行业（free 档原生 SW1 universe）。
- 消费侧零改动：dict 契约不变。
- 解锁历史回填：indices/sectors 升 `historical_safe=True`。

**Non-Goals:**

- 不升级 TickFlow key（保持 free 档）。
- 不引入实时行情 / 分钟K（free 档无，且 market-summary 本就盘后）。
- 不搬 tickflow-stock-panel 的量化能力（选股 / 回测 / 监控）。
- 不引入 Parquet / DuckDB / Polars（保持 SQLite + aiosqlite）。
- 不抓同花顺概念（free 档用申万行业替代，无需外部概念源）。
- 不改公众号文章子系统。

## Decisions

### D1. Provider 抽象——对齐已有 `ArticleListProvider`

新建 `src/api/market_providers/`：`MarketDataProvider(ABC)` + 6 分类方法 + 统一 dataclass 返回 + `name` / `supports_historical` 元数据 + factory。理由：复用团队已熟悉的文章 Provider 范式。

### D2. TickFlow client——free 档简化

- `TickFlow.free()` 单例（free-api 服务器，无需 key）。
- 能力**固定**（日K批量 + 指数日K + SW 行业 universe），无需 tickflow 项目那套复杂的能力探测（5 档探测是为付费档设计的）。仅做一次性可用性探测 + 限流。
- 限流：移植 `rate_limits.py` 的进程级共享时间轴（按 rpm 分桶），60rpm 严格不超。

### D3. 取数路径（free 档重设计——全部基于批量日K + 本地聚合）

| 分类 | free 档实现 | 聚合方式 |
|------|-----------|---------|
| `indices` | `klines.get(指数, period="1d")` | 直接，秒级 |
| `volume` | 盘后全市场日K `amount` | 按 SH/SZ 前缀求和（本地） |
| `statistics` | 盘后全市场日K `change_pct` | count(>0)/count(<0)/count(=0)（本地） |
| `sectors` | SW1 行业成分日K `change_pct` | join 成分 + group_by industry mean（本地） |
| `limit_up` | 盘后全市场日K | filter `change_pct ≥ 9.9%`（本地） |
| `snapshot` | 盘后全市场日K当日 | 直接（本地） |

**关键**：除 indices 外，所有分类都依赖「盘后批量日K落本地 → 本地聚合」。这是 free 档（无实时快照）的唯一路径。

### D4. 板块方案——申万一级行业（替代概念）

- TickFlow free 的 `SW1` universe（~28 个一级行业）直接提供**行业分类 + 成分股**，无需抓同花顺、无需外部概念源。
- 行业涨幅 = 行业成分股日K `change_pct` 聚合求均值。
- 粒度：默认 SW1 一级（~28）；SW2 二级（~100）可选，由配置决定。
- **理由**：free 档无概念 universe，申万行业是其原生提供的最接近"板块"的维度，且成分股直接可取。

### D5. 盘后日K管道（核心新增）

- **触发**：CLI `wchat market-data sync`（独立命令）；可由 `market-summary` 流程在缓存 miss 时按需触发。
- **流程**：
  1. 拉全市场标的列表（`CN_Equity_A` universe 或 instruments）。
  2. `klines.batch` 批量日K（分批 100 标的，60rpm），**增量模式**只拉最新交易日；首次/回填补历史。
  3. 写本地 `daily_kline` 表（原料，按 `(symbol, trade_date)` upsert）。
  4. 触发 D6 本地聚合 → 产出 market_* dict 契约。
- **耗时**：增量 ~1 分钟；首次全量（1 年）~1-2 分钟（batch 一次拿 100 标的的多年日K，批数不变）。
- **幂等**：`(symbol, trade_date)` upsert，重复跑安全。

### D6. 本地聚合层（新增）

从 `daily_kline` 表本地聚合算所有全市场指标，替代 `finance.py` 现有的实时快照聚合：

- 涨跌家数：`count(change_pct > 0)` / `< 0` / `= 0`
- 成交额：`sum(amount)` 按 symbol 前缀（SH/SZ）分组
- 行业涨幅：`daily_kline` join SW1 成员 → `group_by(industry).mean(change_pct)`
- 涨停池：`filter(change_pct ≥ 0.099)`
- 快照：全市场当日 `daily_kline`

用 SQLite SQL 或 Python 聚合（全市场 5500 行，毫秒级）。

### D7. `finance.py` 重构——瘦身为编排器

`SOURCE_STRATEGIES` → Provider 实例元组；adapter 调 Provider + dataclass→dict；`_run_source_strategy` 不变；`get_all_market_data()` dict 契约严格不变。

### D8. dict 契约口径对齐

TickFlow `change_pct` 统一转内部小数口径，规避 `_normalize_pct` 双重缩放坑，单元测试覆盖。

### D9. 本地日K存储

新表 `daily_kline`：`symbol, trade_date, open, high, low, close, volume, amount, change_pct`，PK `(symbol, trade_date)`，schema 自迁移。它是 Provider 聚合的**原料**，与现有 `market_*`（聚合结果）并存。

## Risks / Trade-offs

- **[全市场批量日K耗时]** → 算术推断 ~1 分钟，**需实测确认**（含 free-api 限速节奏与稳定性）。缓解：mixed 模式保留 akshare fallback。
- **[free-api 稳定性]** → 免费服务无强 SLA、可能限速变动。缓解：错误重试 + mixed fallback + 缓存优先。
- **[行业口径冷启动丢历史]** → 41 板块概念趋势归档，按 SW1 重建。接受（用户决策冷启动）。
- **[日K盘后才有]** → 盘中无法生成实时 market-summary。无影响（现状本就盘后）。
- **[SW 粒度选择]** → 一级（~28）/ 二级（~100）/ 三级（~1000）。默认一级，可配。
- **[dict 口径双重缩放]** → D8 单测覆盖。
- **[全市场标的列表来源]** → `CN_Equity_A` universe 是否在 free 档可取（实测样例里未见，需确认），否则用申万行业 universe 聚合或 instruments。

## Migration Plan

**冷启动**（不迁移历史）：

- **Phase 1 — Provider 抽象 + TickFlow free provider + 盘后管道 + `daily_kline`（并存）**
  - 默认 `MARKET_DATA_PROVIDER=mixed`，TickFlow 盘后管道产出与原源并存。
  - 验证：盘后管道能拉全市场日K并聚合，dict 契约不变。

- **Phase 2 — 切主力（盘后管道产出喂 market_*）**
  - statistics/volume/snapshot/sectors/limit_up 主源切本地聚合，pytdx/akshare 降为 fallback。
  - 验证：涨跌家数/成交额与原源对照一致。

- **Phase 3 — 板块口径冷启动（BREAKING）**
  - 归档 `output/sector_trends/` / `output/sector_groups/` + 清空 `tracked_sectors` / `sector_trend_summaries`。
  - 按 SW1 行业重建 tracked 列表 + 重写 `THEME_DEFINITIONS`。
  - **Rollback**：保留原 provider 代码，`MARKET_DATA_PROVIDER=mixed` 切回。

## Open Questions

1. **[已实测 2026-07-19] 全市场批量日K真实耗时**：**56s（0.93 分钟）**，56 批 5528 只 0 失败，符合算术预期。✅ 地基确认。
2. **SW 行业粒度**：一级（~28）vs 二级（~100）？默认一级。
3. **盘后管道触发**：独立 CLI `wchat market-data sync` vs 集成进 market-summary 流程？
4. **首次历史回填范围**：1 年？影响首次耗时。
5. **[已实测 2026-07-19] 全市场标的列表来源**：用 `exchanges.get_instruments(SH/SZ/BJ, instrument_type="stock")` 拿全市场 **5528 只**（SH 2308 + SZ 2892 + BJ 328），秒级。`CN_Equity_A` universe 在 free 档不存在（1013 universe 全是 SW 行业），但无需它。✅ 地基确认。
