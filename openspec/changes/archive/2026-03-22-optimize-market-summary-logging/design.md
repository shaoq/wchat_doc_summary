## Context

`market-summary` 命令当前使用 `console.status()` 显示简单的 spinner，缺乏执行进度和状态信息。

### 当前实现 (cli.py:795-815)

```python
# 获取市场数据
with console.status("[bold blue]获取市场数据...[/bold blue]"):
    market_data = await analyzer.collect_market_data(offline=offline)

# 获取相关文章
with console.status("[bold blue]获取相关文章...[/bold blue]"):
    articles = await analyzer.get_related_articles(trade_date)

# 生成总结
with console.status("[bold blue]AI 生成市场总结...[/bold blue]"):
    content = await processor.generate_market_summary(...)
```

### 参考实现: extract_stocks 命令 (cli.py:660-691)

使用 Rich `Progress` 组件，包含进度条、计数器和动态描述。

## Goals / Non-Goals

**Goals:**
- 分阶段显示执行进度 [1/3], [2/3], [3/3]
- 每阶段完成后显示数据摘要
- AI 生成显示耗时统计
- 离线模式使用醒目的黄色提示
- 使用 Rich Progress 组件提供更好的视觉反馈

**Non-Goals:**
- 不修改底层服务（MarketAnalyzer, AIProcessor, FinanceClient）
- 不添加新的配置项
- 不改变命令行参数

## Decisions

### 1. 使用 `console.status()` + 后置摘要，而非 Progress 进度条

**理由**: Progress 组件适合批量处理（如 extract_stocks 处理多篇文章），但 market-summary 的每个阶段是单次操作，使用 status + 摘要更清晰。

**替代方案**: 使用 Progress 组件显示 3 个阶段的进度条。
**拒绝理由**: 对于单次操作，进度条无法显示实际进度（0% → 100% 在一瞬间完成），用户体验不佳。

### 2. 数据摘要格式

```
[1/3] 获取市场数据...
      ✓ 指数: 上证 3089.26 (+0.45%) | 深证 9876.54 (+0.32%)
      ✓ 成交: 1.2 万亿 | 涨跌: 2500/1800/200

[2/3] 获取相关文章...
      ✓ 找到 15 篇文章 (最近 3 天)

[3/3] AI 生成市场总结...
      ✓ 完成 (耗时 3.2s)
```

**理由**: 简洁明了，一行显示核心信息，不过度占用终端空间。

### 3. 离线模式提示

使用黄色 `[yellow]离线模式[/yellow]` 标签，并在阶段 1 显示 "使用本地数据" 提示。

### 4. 耗时统计

使用 `time.per_counter()` 记录 AI 生成开始和结束时间，精确到小数点后 1 位。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 输出内容过多影响终端体验 | 保持摘要在一行内，使用紧凑格式 |
| 离线模式下数据摘要可能为空 | 显示 "离线模式: 无实时数据" 提示 |
| AI 生成失败时的降级提示 | 显示 "AI 生成失败，使用基础模板" |

## Migration Plan

无需迁移，直接替换现有代码即可。

## Open Questions

无。
