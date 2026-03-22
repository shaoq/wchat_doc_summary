## Context

当前系统已具备 AI 处理能力（摘要、关键词、分类、情感分析），使用 `AIProcessor` 类通过 Anthropic API 调用 LLM。需要新增股票信息提取功能，并引入处理记录机制避免重复调用。

**约束**:
- 复用现有 `AIProcessor` 架构和并发控制机制
- 使用 SQLite 数据库，遵循现有 ORM 模式
- CLI 使用 Click + Rich 保持一致性

## Goals / Non-Goals

**Goals:**
- 实现从文章内容中提取 A股股票信息（名称+代码）
- 创建 `ArticleProcessing` 表记录处理状态
- 支持按公众号批量提取股票信息
- 支持跳过已处理文章，避免重复调用 LLM
- 支持强制重新处理

**Non-Goals:**
- 不存储提取的股票信息到独立表（仅即时输出）
- 不支持港股、美股等其他市场
- 不实现股票信息的历史查询功能

## Decisions

### D1: 处理记录表设计

**决定**: 创建独立的 `ArticleProcessing` 表，而非在 `Article` 表添加字段。

**理由**:
- 可扩展性：未来可支持多种 AI 处理任务（不只是股票提取）
- 解耦：文章内容与处理状态分离
- 灵活性：可记录处理时间、状态、结果等详细信息

**表结构**:
```python
class ArticleProcessing(Base):
    __tablename__ = "article_processing"

    id: int (PK)
    article_id: int (FK → Article.id)
    task_type: str          # "extract_stocks"
    status: str             # "success", "failed", "skipped"
    result: Text            # JSON 格式的提取结果
    processed_at: DateTime
```

### D2: LLM Prompt 设计

**决定**: 使用结构化 Prompt，要求 LLM 返回标准格式的股票列表。

**Prompt 模板**:
```
请从以下文章中提取所有提到的A股股票信息。

要求：
1. 只提取A股股票（沪深两市，代码为6位数字）
2. 格式：股票名称（股票代码）
3. 多个股票用逗号分隔
4. 如果没有提到股票，返回"无"

文章标题：{title}
文章内容：
{content}

股票信息：
```

**备选方案**: 使用 Function Calling / Structured Output
- 优点：输出格式更可靠
- 缺点：需要适配不同 LLM 提供商的 API
- 决定：暂不采用，保持与现有代码一致

### D3: CLI 命令设计

**决定**: 作为 `ai` 子命令组的扩展。

```bash
wchat ai extract-stocks <mp_id> [--output FILE] [--force]
```

**参数**:
- `mp_id`: 必填，公众号 ID
- `--output`: 可选，输出文件路径（不指定则输出到控制台）
- `--force`: 可选，强制重新处理已处理的文章

### D4: 输出格式

**决定**: 简洁的文本格式，按文章分组。

```
文章 #1 《标题...》
  贵州茅台（600519）、宁德时代（300750）

文章 #2 《标题...》
  比亚迪（002594）

[总结] 处理 10 篇，提取 8 只股票
```

## Risks / Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 提取准确率不稳定 | 可能遗漏或错误识别股票 | Prompt 明确规则，后续可优化 |
| 大量文章导致 API 成本高 | 费用增加 | 支持增量处理，记录已处理文章 |
| 股票代码格式不统一 | 输出不一致 | Prompt 中明确6位数字格式 |
