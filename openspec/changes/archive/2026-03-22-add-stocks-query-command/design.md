## Context

股票信息存储在 `article_processing` 表中，`task_type='extract_stocks'`，`result` 字段为 JSON 格式的股票列表如 `["贵州茅台", "宁德时代"]`。需要新增命令来查询这些数据。

## Goals / Non-Goals

**Goals:**
- 查询所有已提取的股票及其出现次数
- 根据股票名称搜索，显示包含该股票的文章
- 查看某公众号提取的所有股票

**Non-Goals:**
- 不修改 extract-stocks 命令
- 不添加股票实时价格查询

## Decisions

### 命令结构

**选择**: 使用子命令模式 `wchat ai stocks <subcommand>`

```
wchat ai stocks list              # 列出所有股票（按出现次数排序）
wchat ai stocks search <关键词>    # 搜索股票，显示相关文章
wchat ai stocks show <股票名>      # 显示某股票详情（出现在哪些文章）
```

**理由**: 子命令模式更清晰，易于扩展。

### 输出格式

**list**: 使用 Rich Table 显示股票名称和出现次数
**search/show**: 显示股票名称 + 文章列表（标题 + 日期）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 股票名称可能不完全一致（如"茅台"vs"贵州茅台"） | 使用 LIKE 模糊匹配 |
