## ADDED Requirements

### Requirement: AI 处理器应能生成市场总结

系统 SHALL 扩展 AIProcessor 支持基于多数据源生成市场总结。

#### Scenario: 生成市场总结
- **WHEN** 用户请求生成市场总结
- **THEN** AI 根据行情数据和文章内容生成结构化总结

#### Scenario: 使用模板生成
- **WHEN** 生成市场总结时
- **THEN** AI 按照用户可编辑的模板格式输出

---

## ADDED Interface

```python
async def generate_market_summary(
    self,
    trade_date: str,
    market_data: dict,
    articles: list[dict],
    template: str | None = None
) -> str:
    """生成市场总结。

    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        market_data: 行情数据（指数、板块、个股等）
        articles: 相关文章列表
        template: 自定义模板（可选）

    Returns:
        市场总结文本
    """
```

## ADDED CLI Commands

```bash
# 自动生成最近交易日总结
wchat ai market-summary

# 指定日期
wchat ai market-summary --date 2026-03-21

# 仅使用已抓取文章（离线模式）
wchat ai market-summary --offline

# 查看历史总结
wchat ai market-summary --list
```

## ADDED Prompts

### 市场总结生成
```
你是一位专业的 A 股市场分析师。请根据以下数据和新闻，生成一份结构化的市场总结报告。

## 模板格式
{template}

## 市场数据
- 日期: {trade_date}
- 指数: {indices}
- 成交额: {volume}
- 涨跌统计: {statistics}
- 板块表现: {sectors}
- 连板个股: {limit_up_stocks}

## 相关新闻
{articles}

请按照模板格式，生成今日市场总结：
```
