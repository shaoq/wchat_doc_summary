## Context

`market-summary` 命令执行时调用链：

```
cli.py
  → ai_processor.generate_market_summary() [主路径]
      → template.format(..., telegraphs=...) ❌ 参数名不匹配
  → market_analyzer.generate_summary() [降级路径]
      → template.format(...) ❌ 缺少 cls_telegrams 参数
```

模板文件 `templates/market_summary.md` 使用 `{cls_telegrams}` 占位符，但代码传递的是 `telegraphs`。

## Goals / Non-Goals

**Goals:**
- 统一模板占位符与代码参数名
- 确保降级路径也能正常工作（传递空值）

**Non-Goals:**
- 不修改模板内容
- 不改变降级逻辑的行为（仍然不包含电报数据）

## Decisions

### D1: 参数命名以模板为准

**决定**: 将代码中的 `telegraphs` 改为 `cls_telegrams`

**理由**:
- 模板是用户可见的配置，修改代码比修改模板影响更小
- `cls_telegrams` 名称更明确表示"财联社电报"

**备选方案**: 修改模板中的 `{cls_telegrams}` 为 `{telegraphs}`
- 不采纳：模板命名更具语义性

### D2: 降级方法传递空字符串

**决定**: `market_analyzer.generate_summary()` 传递 `cls_telegraphs=""`

**理由**:
- 降级逻辑不需要电报数据（用户明确要求）
- 必须传递该参数以避免 KeyError
- 空字符串是语义最清晰的"无数据"表示

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 无 | 这是一个简单的参数名修复，无已知风险 |
