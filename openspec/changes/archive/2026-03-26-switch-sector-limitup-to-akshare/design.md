## Context

当前系统使用东方财富 API（push2.eastmoney.com）获取板块数据和涨停股数据，通过 curl 命令绕过 Python HTTP 库的 TLS 问题。但该 API 在非交易时间持续返回空响应（Exit code 52），导致数据无法获取。

经过测试，以下 akshare 接口可用：
- `stock_sector_spot()` - 新浪行业板块数据，返回 49 个板块
- `stock_zt_pool_em(date)` - 涨停池数据，返回今日涨停股及连板数等

## Goals / Non-Goals

**Goals:**
- 切换板块数据获取方式到 akshare `stock_sector_spot`
- 切换涨停股数据获取方式到 akshare `stock_zt_pool_em`
- 保持现有数据结构兼容，最小化对调用方的影响
- 移除失效的东方财富 curl 降级路径

**Non-Goals:**
- 不修改 cli.py 的命令接口
- 不修改 market_analyzer.py 的调用方式
- 不添加新的数据字段（除非 akshare 接口天然支持）

## Decisions

### 1. 数据源选择

**决定**: 使用 akshare 作为主要数据源

**原因**:
- akshare 的 `stock_sector_spot` 使用新浪数据源，稳定性好
- `stock_zt_pool_em` 虽然底层也是东方财富，但接口封装后可用
- 无需维护 curl 命令绕过逻辑

**备选方案**:
- 继续使用 curl + 东方财富：已证实不可用
- 使用同花顺接口：`stock_board_concept_name_ths` 有 JS 运行时问题

### 2. 板块数据结构调整

**决定**: 保持现有 `SectorData` 模型，映射 akshare 返回字段

**字段映射**:
| akshare 字段 | SectorData 字段 |
|-------------|-----------------|
| 板块 | name |
| 涨跌幅 | change_pct |
| 总成交额 | amount |
| 公司家数 | (新增) stock_count |

### 3. 涨停股数据结构调整

**决定**: 直接使用 akshare 返回的 DataFrame 转换为 dict 列表

**保留字段**:
- 代码、名称、涨跌幅、连板数、封板时间、所属行业

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| akshare 接口可能变更 | 保持接口抽象，便于切换 |
| 新浪板块数据无概念板块 | 行业板块已满足当前需求 |
| 非交易日涨停池为空 | 正常行为，无需特殊处理 |
