# Spec: AI 处理能力

## Capability Description

使用 AI（OpenAI/Anthropic）对文章进行智能处理，包括摘要生成、关键词提取、智能分类和情感分析。

## Interface

### AI 处理器 (AIProcessor)

```python
class AIProcessor:
    def __init__(
        self,
        db: Database,
        provider: str = "openai"
    ):
        """初始化 AI 处理器。

        Args:
            db: 数据库实例
            provider: "openai" 或 "anthropic"
        """

    async def summarize(
        self,
        article_id: int,
        max_length: int = 200
    ) -> str:
        """生成文章摘要。

        从数据库获取文章内容，调用 LLM 生成摘要，
        并更新数据库中的 summary 字段。

        Args:
            article_id: 文章 ID
            max_length: 摘要最大字数

        Returns:
            摘要文本

        Raises:
            ValueError: 文章不存在
        """

    async def extract_keywords(
        self,
        article_id: int,
        max_keywords: int = 10
    ) -> list[str]:
        """提取关键词。

        Args:
            article_id: 文章 ID
            max_keywords: 最大关键词数量

        Returns:
            关键词列表
        """

    async def classify(
        self,
        article_id: int,
        categories: list[str] | None = None
    ) -> str:
        """智能分类。

        Args:
            article_id: 文章 ID
            categories: 自定义分类列表，默认使用：
                       科技、财经、教育、娱乐、健康、
                       政治、社会、体育、其他

        Returns:
            分类名称
        """

    async def analyze_sentiment(
        self,
        article_id: int
    ) -> str:
        """情感分析。

        Args:
            article_id: 文章 ID

        Returns:
            "positive", "negative", 或 "neutral"
        """

    async def batch_summarize(
        self,
        article_ids: list[int],
        max_length: int = 200
    ) -> dict[int, str]:
        """批量生成摘要。

        并发处理多篇文章，带请求限流。

        Args:
            article_ids: 文章 ID 列表
            max_length: 摘要最大字数

        Returns:
            {article_id: summary} 字典
        """
```

## Configuration

环境变量配置：

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

## CLI Commands

```bash
# 生成摘要
wchat ai summarize 1

# 提取关键词
wchat ai keywords 1 --max-keywords 10

# 智能分类
wchat ai classify 1

# 情感分析
wchat ai sentiment 1

# 批量处理
wchat ai batch-summarize --mp-id MP_WXS_xxx --batch-size 10
```

## Usage Example

```python
from src.storage.database import get_db
from src.services.ai_processor import AIProcessor

async def example():
    db = await get_db()

    # 使用 OpenAI
    processor = AIProcessor(db, provider="openai")

    # 生成摘要
    summary = await processor.summarize(article_id=1, max_length=200)
    print(f"摘要: {summary}")

    # 提取关键词
    keywords = await processor.extract_keywords(article_id=1, max_keywords=5)
    print(f"关键词: {', '.join(keywords)}")

    # 智能分类
    category = await processor.classify(article_id=1)
    print(f"分类: {category}")

    # 情感分析
    sentiment = await processor.analyze_sentiment(article_id=1)
    print(f"情感: {sentiment}")

    # 批量处理
    results = await processor.batch_summarize([1, 2, 3, 4, 5])
    for aid, summ in results.items():
        print(f"文章 {aid}: {summ}")
```

## Prompts

### 摘要生成
```
请为以下文章生成一个简洁的摘要，不超过 {max_length} 字。

文章标题：{title}
文章内容：
{content}

摘要：
```

### 关键词提取
```
请从以下文章中提取 {max_keywords} 个关键词。

文章标题：{title}
文章内容：
{content}

关键词（用逗号分隔）：
```

### 智能分类
```
请将以下文章分类到最合适的类别中。

可选类别：{categories}

文章标题：{title}
文章内容摘要：{summary}

类别：
```

## Rate Limiting

- 并发限制：Semaphore(5)
- 请求间隔：0.5 秒
- 重试机制：指数退避，最大 3 次

## Error Handling

| Error | Cause | Handling |
|-------|-------|----------|
| API Key 无效 | 配置错误 | 抛出异常，提示检查配置 |
| 文章不存在 | article_id 无效 | ValueError |
| 内容为空 | 文章未抓取 | ValueError |
| Rate Limit | 请求过快 | 自动重试 |
| 网络错误 | 连接失败 | 重试机制 |

---

## ADDED Requirements

### Requirement: AI market summary generation shall organize evidence before strategy synthesis

The system SHALL present market-summary inputs to the model as explicit evidence groups so that strategy guidance is derived from structured facts rather than loosely concatenated raw text.

#### Scenario: Prompt groups evidence by analysis role
- **WHEN** `AIProcessor.generate_market_summary()` prepares a market-summary prompt
- **THEN** the prompt SHALL separate market snapshot, sector signals, stock-leadership clues, telegraph catalysts, watch-item rotation clues, and article viewpoints into distinct analysis groups

#### Scenario: Prompt discloses missing evidence
- **WHEN** one or more key evidence groups are empty or unreliable
- **THEN** the prompt SHALL explicitly state those gaps to the model
- **AND** the model SHALL be instructed to downgrade strategy confidence accordingly

### Requirement: AI strategy guidance shall be evidence-bound

The system SHALL require market-summary strategy guidance to reference explicit supporting signals and corresponding risks.

#### Scenario: Strategy guidance includes supporting basis
- **WHEN** the model outputs follow-up strategy guidance
- **THEN** each guidance item SHALL be tied to at least one explicit market, news, sector, or stock signal from the input evidence

#### Scenario: Strategy guidance includes risk or invalidation cues
- **WHEN** the model outputs follow-up strategy guidance
- **THEN** the output SHALL include corresponding risk reminders, invalidation cues, or fallback observation points

### Requirement: AI content-safety retry SHALL be stage-aware

The AI processing layer SHALL identify the logical generation stage when handling provider content-safety failures so callers and logs can distinguish required generation from optional enrichment.

#### Scenario: Content-safety log identifies generation stage
- **WHEN** an AI call fails due to provider content safety review
- **THEN** the retry or failure log SHALL include enough stage context to identify the failed operation
- **AND** market-summary callers SHALL be able to distinguish initial summary generation from strategy enhancement

#### Scenario: Repeated safety rejection does not hide unchanged retry input
- **WHEN** a prompt has already been sanitized after a content-safety failure
- **AND** subsequent retries still fail due to content safety review
- **THEN** the system SHALL NOT imply that additional sanitization was applied
- **AND** the final error path SHALL preserve the original provider error for diagnostics

### Requirement: AI prompt sanitization SHALL preserve structured factual evidence

The AI processing layer SHALL remove or mask risky free-text content without distorting structured factual evidence used by downstream summaries.

#### Scenario: Sanitization preserves market-data facts
- **WHEN** sanitization is applied to a market-summary prompt containing numeric and structured market facts
- **THEN** the sanitized prompt SHALL preserve index values, turnover, breadth counts, sector names, stock names, and source availability statements unless the exact free-text item is removed as risky content

#### Scenario: Sanitization marks removed event evidence as unavailable
- **WHEN** sanitization removes or masks event-title evidence from an AI prompt
- **THEN** the remaining prompt SHALL retain enough context for the model to treat that event class as unavailable or insufficient
- **AND** the prompt SHALL NOT convert removed event evidence into a stronger market conclusion
