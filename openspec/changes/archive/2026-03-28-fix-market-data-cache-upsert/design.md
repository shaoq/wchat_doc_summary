## Context

当前 `market-summary` 在当前交易日执行 `--force` 时，会跳过读取缓存并重新抓取在线行情，然后尝试把结果重新写入市场数据缓存。问题在于缓存层对 `market_indices`、`market_volume`、`market_statistics` 以及复合唯一键表的写入使用了 `session.merge()`，而这些表的业务唯一键是 `trade_date` 或 `(trade_date, code)`，不是 ORM 主键 `id`。在已有缓存记录的情况下，这种写法会走插入路径并触发 SQLite 唯一约束错误。

这个问题横跨 CLI 触发路径、`MarketAnalyzer` 编排层和 `MarketDataCacheService` 持久化层。修复需要同时明确“什么叫覆盖缓存”和“缓存层如何按业务唯一键执行 upsert”，否则 `--force` 语义仍然会和实际行为脱节。

## Goals / Non-Goals

**Goals:**
- 让同一交易日的市场数据缓存保存操作具备幂等性。
- 让 `market-summary --force` 在已有市场数据缓存时能够稳定完成。
- 为单行缓存表和复合唯一键缓存表定义一致的覆盖写入语义。
- 补齐重复保存场景的数据库级回归测试。

**Non-Goals:**
- 不修改市场数据表结构或新增迁移。
- 不引入新的缓存介质或数据库依赖。
- 不改变历史交易日“不支持在线强刷”的既有策略。

## Decisions

### 1. 缓存层改为“按业务唯一键查询后更新/插入”，而不是依赖 `merge()`

选择：在 `MarketDataCacheService.save_market_data()` 内对每类缓存记录显式执行 upsert：
- `MarketIndex` / `MarketVolume` / `MarketStatistics` 按 `trade_date` 查询
- `MarketSector` 按 `(trade_date, sector_code)` 查询
- `LimitUpStock` 按 `(trade_date, stock_code)` 查询

理由：
- 现有 schema 的唯一性约束建立在业务键上，而 `merge()` 只可靠识别主键。
- 查询后更新/插入和现有 `MarketSummary.save_summary()` 的模式一致，代码语义清晰。
- 该方案不依赖特定数据库方言，适合当前 SQLite 基线。

备选方案：
- 使用 SQLite `INSERT ... ON CONFLICT DO UPDATE`。优点是更直接，缺点是实现更偏方言，削弱 ORM 层一致性。
- 在写入前先删后插。优点是简单，缺点是会放大写入范围，也更容易误删未覆盖到的同日数据。

### 2. `--force` 的“覆盖缓存”语义保持在分析器层，缓存幂等性收敛在缓存服务层

选择：`MarketAnalyzer.collect_market_data(force=True)` 继续负责“跳过读取旧缓存并重新抓在线数据”，`MarketDataCacheService` 负责保证写入不会因已有记录失败。

理由：
- 分层清晰，分析器负责流程控制，缓存服务负责持久化语义。
- 不需要在 CLI 层特殊处理数据库错误或显式删除缓存。

备选方案：
- 在分析器层先调用删除缓存再写入。缺点是流程更脆弱，且把缓存表细节泄漏到上层编排。

### 3. 用数据库级重复保存测试锁定回归

选择：为 `save_market_data()` 增加“同一交易日连续保存两次”的测试，并覆盖单行表更新和复合唯一键表更新。

理由：
- 本次缺陷只有在第二次保存时才会暴露，mock 级测试不足以覆盖。
- 数据库级测试能直接验证“不抛 UNIQUE constraint”和“最终只保留一份当前值”。

备选方案：
- 只补单元测试验证调用次数。缺点是无法捕捉 SQLite 唯一约束冲突这一真实失效模式。

## Risks / Trade-offs

- [逐类查询后再更新会增加少量 SQL 次数] → 当前缓存写入频率低，优先保证语义正确；后续若需要可再评估批量 upsert。
- [top/bottom 板块或涨停股榜单缩短时，旧记录可能残留] → 本次至少确保同键覆盖不报错；如需“严格镜像当前榜单”，可在后续 change 中单独收紧删除语义。
- [重复保存会更新 `fetch_time`，但保留原始 `created_at`] → 这符合“缓存刷新”语义，也避免像删后插那样改变记录身份。
