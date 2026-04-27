## Context

当前系统在执行 `market-summary` 时，每次都通过 `FinanceClient` 调用外部 API 获取市场数据：
- 指数数据（新浪）
- 成交额（新浪）
- 涨跌统计（新浪）
- 板块数据（东方财富）
- 涨停股（akshare）

这些数据在收盘后（15:00）就不会再变化，但目前没有本地缓存机制。

**已有参考实现**：
- `CLSTelegraphService` - 电报数据的存储和查询服务
- `CLSTelegraph` / `CLSWatchData` - 类似的数据持久化模式

## Goals / Non-Goals

**Goals:**
- 收盘后（15:00）自动缓存获取到的市场数据
- 后续查询同一交易日时优先返回缓存数据
- 减少对外部 API 的重复调用
- 支持强制刷新缓存

**Non-Goals:**
- 不支持实时数据缓存（盘中数据不缓存）
- 不支持历史数据补抓（API 可能只提供当日数据）
- 不修改现有 API 客户端（`FinanceClient`）的接口

## Decisions

### D1: 分表存储（而非单一 JSON 快照表）

**选择**: 为每种数据类型创建独立的表

**理由**:
- 结构化存储，便于单独查询和维护
- 板块和涨停股数据量大，独立表更高效
- 与现有 `CLSTelegraph` 模式一致

**备选方案**:
- 单一快照表（JSON 字段）：实现简单，但查询和更新不灵活

### D2: 涨停股独立建表

**选择**: 创建 `limit_up_stocks` 表，每只股票一行

**理由**:
- 涨停股数量可能较多（20+ 条）
- 每条有独立字段（代码、名称、连板数、行业）
- 便于后续按股票代码查询历史涨停记录

### D3: 缓存判断逻辑

**选择**:
1. 先查数据库，有缓存则返回
2. 无缓存则调用 API
3. 如果当前时间 > 15:00 且是交易日，存储数据

```python
def should_cache(trade_date: date) -> bool:
    today = date.today()
    now = datetime.now()

    # 历史日期：可以缓存（但 API 可能无法获取历史数据）
    if trade_date < today:
        return True

    # 今天：需判断是否收盘
    if trade_date == today:
        return now.time() > time(15, 5)  # 15:05 作为缓冲

    return False
```

### D4: 服务层位置

**选择**: 新建 `MarketDataCacheService`，由 `MarketAnalyzer` 调用

**理由**:
- 遵循单一职责原则
- 与 `CLSTelegraphService` 模式一致
- `FinanceClient` 保持纯粹的数据获取职责

## Risks / Trade-offs

### R1: 历史数据无法补抓
- **风险**: API 可能只提供当日数据，历史日期的缓存可能永远为空
- **缓解**: 这是预期行为，用户需要理解历史数据依赖当时的缓存

### R2: 缓存数据错误
- **风险**: 如果 API 返回错误数据，会被缓存
- **缓解**: 提供 `--force` 参数强制刷新；提供 CLI 命令删除指定日期缓存

### R3: 部分获取成功
- **风险**: 5 种数据可能部分成功部分失败
- **缓解**: 每种数据独立存储，成功的存储，失败的不影响其他

### R4: 表结构冗余
- **风险**: 5 张表增加了维护成本
- **缓解**: 使用统一的 ORM 模式，服务层封装访问逻辑
