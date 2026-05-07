## Context

当前 `wchat fetch --all` 的抓取流程是完全无状态的：每次运行都从 `list_subscriptions_for_fetch()` 获取完整的订阅列表，按固定排序（weight DESC → sync_time IS NULL → name ASC）从头遍历。当遇到 `RateLimitError` 时，循环 break，后续订阅全部跳过。用户重新执行时，排序不变，前面的订阅再次被抓取（重复消耗 API 配额），后面的订阅始终无法触达。

数据库为 SQLite + aiosqlite，ORM 为 SQLAlchemy。已有的 `feeds` 表存储订阅信息（含 `sync_time`、`weight`、`status` 字段）。

## Goals / Non-Goals

**Goals:**

- `fetch --all` 限流中断后重跑，自动跳过已完成的订阅，从断点处继续
- 每日自动重置进度，新的一天全新开始
- 当天新增订阅自动纳入 batch
- 全部完成后给出提示，避免无效 API 调用
- `wchat fetch <mp_id>` 单独抓取不受影响

**Non-Goals:**

- 不实现跨天的进度延续（第二天必须全新开始）
- 不实现并发 session（CLI 工具无此需求）
- 不修改单个订阅抓取（`fetch <mp_id>`）的行为
- 不修改 rate_limiter 或 circuit breaker 的限流策略

## Decisions

### D1: 单表设计 vs 两表设计

**选择：单表 `fetch_batches`**

```python
class FetchBatch(Base):
    __tablename__ = "fetch_batches"

    id:         Mapped[int]      # PK
    mp_id:      Mapped[str]      # 关联 feeds.mp_id
    batch_date: Mapped[date]     # 天然实现每日隔离
    status:     Mapped[str]      # "pending" | "done"
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    UniqueConstraint("mp_id", "batch_date")
```

**替代方案**：Session + SessionItem 两表设计，需要 JOIN 查询，且 CLI 工具不存在并发 session 的场景，过度设计。

**理由**：`batch_date` 天然隔离每日进度，无需额外的 session 管理逻辑。单表查询简单高效。

### D2: 状态设计 — 两个状态 vs 多状态

**选择：两状态（pending / done）**

| 状态 | 含义 | 恢复时行为 |
|------|------|-----------|
| `pending` | 未完成或被中断 | 继续抓取 |
| `done` | 成功完成或非致命错误已尝试 | 跳过 |

**理由**：
- RateLimitError 中断时，当前 feed 不确定是否完成 → 保持 `pending`，重跑时重试
- 非 fatal error（网络抖动等）→ 标记 `done`，与现有 `fetch_all` 行为一致（继续下一个）
- 无需区分 `error` / `rate_limited` 等细分状态，简化逻辑

### D3: 进度写入时机

**选择：每完成一个 feed 即写入**

- 成功：立即 UPDATE status='done'
- 非 fatal error：立即 UPDATE status='done'
- RateLimitError：不写入（保持 pending），break

**理由**：SQLite WAL 模式下写入开销极低。即使进程崩溃，已完成的 feed 不会丢失。

### D4: 排序策略

**选择：恢复时沿用现有权重排序**

```
首次:  feeds = list_subscriptions_for_fetch()  → 按 weight DESC, sync_time IS NULL, name ASC
恢复:  feeds = pending feeds → JOIN feeds → 同样按 weight DESC, name ASC
```

不存储 `sort_order` 字段，因为：
- 权重和名称在同一日内不会变化
- 重算排序成本低（SQLite 内存排序）
- 避免额外字段维护

### D5: CLI 交互

```
wchat fetch --all           → 自动 batch 续传
wchat fetch --all --force   → 清除今日 batch，全新开始
wchat fetch MP_xxx          → 不受 batch 影响
```

全部完成时输出：`[green]今日所有订阅已同步完成[/green]`，不再发起任何 API 调用。

### D6: 旧数据清理

**选择：保留 7 天，启动时自动清理**

在 `fetch_all` 开始时执行 `DELETE FROM fetch_batches WHERE batch_date < date('now', '-7 days')`。记录量极小（每天每个活跃订阅一条），7 天足够排查问题。

## Risks / Trade-offs

- **[已取消订阅的残留记录]** → batch 查询时 JOIN feeds 表且 `status=1`，已取消的订阅自然被过滤
- **[数据库锁竞争]** → SQLite WAL 模式下读写不互斥；batch 操作是简单的单行 UPDATE，不构成瓶颈
- **[时钟回拨]** → `batch_date` 使用 Python `date.today()`，不依赖单调时钟，极端情况下（系统时间被手动调回前一天）可能导致 batch 复用。风险极低，不额外处理
- **[feed 数量暴增]** → 单表 + 索引（batch_date, mp_id），即使数百订阅也无性能问题
