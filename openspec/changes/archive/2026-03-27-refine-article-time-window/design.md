## Context

市场总结功能需要获取与特定交易日相关的公众号文章。当前实现使用简单的 `days_back` 参数，获取交易日前后几天的所有文章，没有考虑交易日的精确时间边界。

**当前状态**:
- `get_related_articles(trade_date, days_back=3)` 查询 `trade_date - 3天` 到 `trade_date + 1天` 的文章
- 没有精确的时间窗口概念
- 使用 `chinese_calendar.is_workday()` 判断交易日

## Goals / Non-Goals

**Goals:**
- 实现基于交易日的精确时间窗口计算
- 正确处理周末和节假日
- 在 CLI 输出中显示时间窗口

**Non-Goals:**
- 不修改数据库 schema
- 不修改 AI 生成逻辑
- 不添加新的外部依赖

## Decisions

### 1. 时间窗口定义

**决定**: 窗口起点为交易日 15:00，终点为下一交易日 09:15

**理由**:
- 15:00 是 A 股收盘时间，收盘后的文章属于当日盘后分析
- 09:15 是集合竞价开始时间，之前的文章仍属于前一交易日的复盘

**备选方案**:
- 使用 09:30（开盘时间）作为终点 - 否决，因为 09:15-09:30 的文章仍是对前日的评论

### 2. 下一交易日计算

**决定**: 新增 `get_next_trade_date(date)` 方法，从给定日期的下一天开始往后找

**理由**:
- 简单明确：从 date + 1 天开始检查
- 复用现有的 `chinese_calendar.is_workday()` 判断

**实现**:
```python
def get_next_trade_date(self, date: date) -> date:
    check_date = date + timedelta(days=1)
    max_days = 30
    for _ in range(max_days):
        if calendar.is_workday(check_date):
            return check_date
        check_date += timedelta(days=1)
    return check_date  # 降级返回
```

### 3. 时间窗口方法设计

**决定**: 新增 `get_article_time_window(trade_date)` 返回 `(datetime, datetime)` 元组

**理由**:
- 封装时间窗口计算逻辑
- 便于测试和复用
- 便于在 CLI 中打印

### 4. CLI 输出格式

**决定**: 在获取文章步骤显示时间窗口

**格式**:
```
[2/3] 获取相关文章...
      时间窗口: 2026-03-21 15:00 ~ 2026-03-24 09:15
      ✓ 找到 15 篇文章
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| chinese_calendar 数据过期 | 库会定期更新年度假期；可手动升级 |
| 30 天内找不到交易日 | 降级返回最后检查的日期并记录警告 |
| 时区问题 | 使用本地时区 (中国标准时间) |
