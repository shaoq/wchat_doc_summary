"""AI 处理服务模块 - 提供文章摘要、关键词提取、分类等功能。"""

import asyncio
import logging
from collections.abc import Callable

from anthropic import AsyncAnthropic

from config.settings import get_settings
from src.models.schema import Article, ArticleProcessing
from src.storage.database import Database, CRUDOperations

logger = logging.getLogger(__name__)

# 默认分类列表
DEFAULT_CATEGORIES = [
    "科技",
    "财经",
    "教育",
    "娱乐",
    "健康",
    "政治",
    "社会",
    "体育",
    "其他",
]

# 提示词模板
SUMMARIZE_PROMPT = """请为以下文章生成一个简洁的摘要，不超过 {max_length} 字。

文章标题：{title}
文章内容：
{content}

摘要："""

KEYWORDS_PROMPT = """请从以下文章中提取 {max_keywords} 个关键词。

文章标题：{title}
文章内容：
{content}

关键词（用逗号分隔）："""

CLASSIFY_PROMPT = """请将以下文章分类到最合适的类别中。

可选类别：{categories}

文章标题：{title}
文章内容摘要：{summary}

只需要返回类别名称，不需要其他内容。"""

SENTIMENT_PROMPT = """请分析以下文章的情感倾向。

文章标题：{title}
文章内容摘要：{content}

请只返回以下三个选项之一：positive（正面）、negative（负面）、neutral（中立）

情感："""

EXTRACT_STOCKS_PROMPT = """请从以下文章中提取所有提到的A股股票信息。

要求：
1. 只提取A股股票（沪深两市，代码为6位数字）
2. 格式：股票名称（股票代码）
3. 多个股票用逗号分隔
4. 如果没有提到股票，返回"无"
5. 确保股票代码准确（6位数字）

文章标题：{title}
文章内容：
{content}

股票信息："""

MARKET_SUMMARY_PROMPT = """你是一位专业的 A 股市场分析师。请根据以下数据和新闻，生成一份结构化的市场总结报告。

## 交易日期
{trade_date}

## 市场数据
### 指数表现
{indices_summary}

### 成交情况
两市成交额：{volume} 亿元

### 涨跌统计
- 上涨：{up_count} 家
- 下跌：{down_count} 家
- 平盘：{flat_count} 家

### 板块表现
涨幅榜：{top_sectors}
跌幅榜：{bottom_sectors}

### 涨停个股
{limit_up_stocks}

## 相关新闻
{articles}

请生成一份专业的市场总结报告，包含以下部分：
1. 市场概览（指数表现、成交情况、涨跌统计）
2. 板块分析（热点板块、弱势板块）
3. 个股亮点（涨停股、龙头股）
4. 市场消息（核心新闻摘要）

报告要求：
- 语言简洁专业
- 突出重点信息
- 结合数据和市场消息进行分析
- 总字数控制在 500-800 字

市场总结报告："""


class AIProcessor:
    """AI 处理服务类。

    支持任意兼容 Anthropic 协议的 LLM 平台。
    """

    def __init__(self, db: Database) -> None:
        """初始化 AI 处理器。

        Args:
            db: 数据库实例

        Raises:
            ValueError: LLM API Key 未配置
        """
        self.db = db
        self.settings = get_settings()
        self._article_crud = CRUDOperations(Article)

        api_key = self.settings.llm_api_key
        if not api_key:
            raise ValueError("LLM API Key 未配置，请设置 LLM_API_KEY")

        self.client = AsyncAnthropic(
            api_key=api_key,
            base_url=self.settings.llm_base_url,
        )
        self.model = self.settings.llm_model

        self._request_semaphore = asyncio.Semaphore(5)
        self._request_interval = 0.5

    async def summarize(self, article_id: int, max_length: int = 200) -> str:
        """生成文章摘要。

        Args:
            article_id: 文章 ID
            max_length: 摘要最大字数

        Returns:
            生成的摘要文本

        Raises:
            ValueError: 文章不存在或内容为空
        """
        async with self.db.get_session() as session:
            article = await self._article_crud.get(session, article_id)
            if not article:
                raise ValueError(f"文章 ID {article_id} 不存在")

            if not article.content:
                raise ValueError(f"文章 ID {article_id} 内容为空")

            prompt = self._build_prompt(
                "summarize",
                article.content,
                title=article.title,
                max_length=max_length,
            )

            summary = await self._call_api(prompt, max_tokens=max_length * 2)

            await self._article_crud.update(session, article, {"summary": summary})
            logger.info(f"文章 {article_id} 摘要生成完成")

            return summary

    async def extract_keywords(
        self,
        article_id: int,
        max_keywords: int = 10,
    ) -> list[str]:
        """提取文章关键词。

        Args:
            article_id: 文章 ID
            max_keywords: 最大关键词数量

        Returns:
            关键词列表
        """
        async with self.db.get_session() as session:
            article = await self._article_crud.get(session, article_id)
            if not article:
                raise ValueError(f"文章 ID {article_id} 不存在")

            content = article.content or ""
            prompt = self._build_prompt(
                "keywords",
                content,
                title=article.title,
                max_keywords=max_keywords,
            )

            result = await self._call_api(prompt, max_tokens=200)
            keywords = [kw.strip() for kw in result.split(",") if kw.strip()]

            logger.info(f"文章 {article_id} 关键词提取完成: {keywords}")
            return keywords[:max_keywords]

    async def classify(
        self,
        article_id: int,
        categories: list[str] | None = None,
    ) -> str:
        """智能分类文章。

        Args:
            article_id: 文章 ID
            categories: 自定义分类列表，默认使用 DEFAULT_CATEGORIES

        Returns:
            分类名称
        """
        categories = categories or DEFAULT_CATEGORIES

        async with self.db.get_session() as session:
            article = await self._article_crud.get(session, article_id)
            if not article:
                raise ValueError(f"文章 ID {article_id} 不存在")

            summary = article.summary or ""
            if not summary and article.content:
                summary = article.content[:500]

            prompt = self._build_prompt(
                "classify",
                summary,
                title=article.title,
                categories="、".join(categories),
            )

            result = await self._call_api(prompt, max_tokens=50)
            category = result.strip()

            if category not in categories:
                category = "其他"

            logger.info(f"文章 {article_id} 分类完成: {category}")
            return category

    async def batch_summarize(
        self,
        article_ids: list[int],
        max_length: int = 200,
    ) -> dict[int, str]:
        """批量生成文章摘要。

        Args:
            article_ids: 文章 ID 列表
            max_length: 摘要最大字数

        Returns:
            {article_id: summary} 字典
        """
        results: dict[int, str] = {}
        errors: dict[int, str] = {}

        async def process_one(article_id: int) -> None:
            try:
                summary = await self.summarize(article_id, max_length)
                results[article_id] = summary
            except Exception as e:
                errors[article_id] = str(e)
                logger.error(f"处理文章 {article_id} 失败: {e}")

        await asyncio.gather(*[process_one(aid) for aid in article_ids])

        if errors:
            logger.warning(f"批量处理完成，{len(errors)} 篇文章处理失败")

        return results

    async def analyze_sentiment(self, article_id: int) -> str:
        """分析文章情感。

        Args:
            article_id: 文章 ID

        Returns:
            情感标签: positive, negative, neutral
        """
        async with self.db.get_session() as session:
            article = await self._article_crud.get(session, article_id)
            if not article:
                raise ValueError(f"文章 ID {article_id} 不存在")

            content = article.summary or article.content or ""
            if len(content) > 1000:
                content = content[:1000]

            prompt = self._build_prompt(
                "sentiment",
                content,
                title=article.title,
            )

            result = await self._call_api(prompt, max_tokens=20)
            sentiment = result.strip().lower()

            valid_sentiments = ["positive", "negative", "neutral"]
            if sentiment not in valid_sentiments:
                sentiment = "neutral"

            logger.info(f"文章 {article_id} 情感分析完成: {sentiment}")
            return sentiment

    async def extract_stocks(self, article_id: int) -> list[str]:
        """提取文章中的股票信息。

        Args:
            article_id: 文章 ID

        Returns:
            股票信息列表，格式为 ["股票名称（股票代码）", ...]
        """
        async with self.db.get_session() as session:
            article = await self._article_crud.get(session, article_id)
            if not article:
                raise ValueError(f"文章 ID {article_id} 不存在")

            content = article.content or ""
            if not content:
                raise ValueError(f"文章 ID {article_id} 内容为空")

            prompt = self._build_prompt(
                "extract_stocks",
                content,
                title=article.title,
            )

            result = await self._call_api(prompt, max_tokens=500)
            result = result.strip()

            # 解析结果
            if result == "无" or not result:
                stocks = []
            else:
                stocks = [s.strip() for s in result.split("，") if s.strip()]
                # 也尝试用英文逗号分割
                if len(stocks) == 1 and "," in stocks[0]:
                    stocks = [s.strip() for s in stocks[0].split(",") if s.strip()]

            logger.info(f"文章 {article_id} 股票提取完成: {stocks}")
            return stocks

    async def batch_extract_stocks(
        self,
        article_ids: list[int],
        force: bool = False,
        concurrency_limit: int = 3,
        progress_callback: Callable | None = None,
    ) -> dict[int, list[str]]:
        """批量提取文章股票信息。

        Args:
            article_ids: 文章 ID 列表
            force: 是否强制重新处理已处理的文章
            concurrency_limit: 并发限制数，默认 3
            progress_callback: 进度回调函数，参数为 (article_id, status, stocks_or_error)

        Returns:
            {article_id: [stocks]} 字典
        """
        import json

        results: dict[int, list[str]] = {}
        errors: dict[int, str] = {}
        skipped: list[int] = []

        # 获取已处理的文章
        if not force:
            processed_ids = await self._get_processed_articles(article_ids, "extract_stocks")
        else:
            processed_ids = set()

        # 并发控制
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def process_one(article_id: int) -> None:
            if article_id in processed_ids:
                skipped.append(article_id)
                logger.info(f"文章 {article_id} 已处理，跳过")
                if progress_callback:
                    progress_callback(article_id, "skipped", None)
                return

            async with semaphore:
                try:
                    stocks = await self.extract_stocks(article_id)
                    results[article_id] = stocks

                    # 记录处理结果
                    await self._record_processing(
                        article_id,
                        "extract_stocks",
                        "success",
                        json.dumps(stocks, ensure_ascii=False),
                    )

                    if progress_callback:
                        progress_callback(article_id, "success", stocks)
                except Exception as e:
                    errors[article_id] = str(e)
                    logger.error(f"处理文章 {article_id} 失败: {e}")

                    # 记录失败
                    await self._record_processing(
                        article_id,
                        "extract_stocks",
                        "failed",
                        json.dumps({"error": str(e)}, ensure_ascii=False),
                    )

                    if progress_callback:
                        progress_callback(article_id, "failed", str(e))

        await asyncio.gather(*[process_one(aid) for aid in article_ids])

        if errors:
            logger.warning(f"批量处理完成，{len(errors)} 篇文章处理失败")
        if skipped:
            logger.info(f"跳过 {len(skipped)} 篇已处理文章")

        return results

    async def _get_processed_articles(
        self,
        article_ids: list[int],
        task_type: str,
    ) -> set[int]:
        """获取已处理的文章 ID 集合。

        Args:
            article_ids: 待检查的文章 ID 列表
            task_type: 任务类型

        Returns:
            已处理的文章 ID 集合
        """
        from sqlalchemy import select

        async with self.db.get_session() as session:
            result = await session.execute(
                select(ArticleProcessing.article_id).where(
                    ArticleProcessing.article_id.in_(article_ids),
                    ArticleProcessing.task_type == task_type,
                    ArticleProcessing.status == "success",
                )
            )
            return set(result.scalars().all())

    async def _record_processing(
        self,
        article_id: int,
        task_type: str,
        status: str,
        result: str | None = None,
    ) -> None:
        """记录文章处理结果。

        Args:
            article_id: 文章 ID
            task_type: 任务类型
            status: 状态 (success, failed, skipped)
            result: 处理结果 (JSON 字符串)
        """
        processing_crud = CRUDOperations(ArticleProcessing)

        async with self.db.get_session() as session:
            await processing_crud.create(
                session,
                {
                    "article_id": article_id,
                    "task_type": task_type,
                    "status": status,
                    "result": result,
                },
            )

    def _build_prompt(self, task: str, content: str, **kwargs: str | int) -> str:
        """构建提示词。

        Args:
            task: 任务类型
            content: 文章内容
            **kwargs: 其他参数

        Returns:
            构建好的提示词
        """
        templates = {
            "summarize": SUMMARIZE_PROMPT,
            "keywords": KEYWORDS_PROMPT,
            "classify": CLASSIFY_PROMPT,
            "sentiment": SENTIMENT_PROMPT,
            "extract_stocks": EXTRACT_STOCKS_PROMPT,
        }

        template = templates.get(task, "")
        return template.format(content=content, **kwargs)

    async def _call_api(self, prompt: str, max_tokens: int = 500) -> str:
        """调用 LLM API。

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数

        Returns:
            LLM 响应文本
        """
        async with self._request_semaphore:
            await asyncio.sleep(self._request_interval)

            for attempt in range(self.settings.max_retries + 1):
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}],
                    )

                    content = response.content[0]
                    return content.text if hasattr(content, "text") else str(content)

                except Exception as e:
                    if attempt < self.settings.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"API 调用失败 (尝试 {attempt + 1}/{self.settings.max_retries + 1})，"
                            f"{wait_time}秒后重试: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"API 调用最终失败: {e}")
                        raise

        raise RuntimeError("不应该到达这里")

    async def generate_market_summary(
        self,
        trade_date: str,
        market_data: dict,
        articles: list[dict],
    ) -> str:
        """生成市场总结。

        Args:
            trade_date: 交易日期 (YYYY-MM-DD)
            market_data: 行情数据（指数、板块、个股等）
            articles: 相关文章列表

        Returns:
            市场总结文本
        """
        # 格式化数据
        indices = market_data.get("indices", {})
        indices_summary = self._format_indices_for_prompt(indices)

        volume = market_data.get("volume", {}).get("total_volume", "N/A")
        stats = market_data.get("statistics", {})
        sectors = market_data.get("sectors", {})
        limit_up = market_data.get("limit_up", [])

        # 格式化板块
        top_sectors = self._format_sectors_for_prompt(sectors.get("top_sectors", []))
        bottom_sectors = self._format_sectors_for_prompt(sectors.get("bottom_sectors", []))

        # 格式化个股
        limit_up_stocks = self._format_stocks_for_prompt(limit_up[:10])

        # 格式化文章
        articles_text = self._format_articles_for_prompt(articles[:10])

        # 构建提示词
        prompt = MARKET_SUMMARY_PROMPT.format(
            trade_date=trade_date,
            indices_summary=indices_summary,
            volume=volume,
            up_count=stats.get("up_count", "N/A"),
            down_count=stats.get("down_count", "N/A"),
            flat_count=stats.get("flat_count", "N/A"),
            top_sectors=top_sectors,
            bottom_sectors=bottom_sectors,
            limit_up_stocks=limit_up_stocks,
            articles=articles_text,
        )

        # 调用 API
        logger.info(f"开始生成市场总结: {trade_date}")
        summary = await self._call_api(prompt, max_tokens=1500)
        logger.info(f"市场总结生成完成")

        return summary

    def _format_indices_for_prompt(self, indices: dict) -> str:
        """格式化指数数据用于 prompt。"""
        if not indices:
            return "数据获取失败"

        lines = []
        for key, data in indices.items():
            name = data.get("name", key)
            close = data.get("close", 0)
            change = data.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}: {close:.2f} ({sign}{change*100:.2f}%)")

        return "\n".join(lines)

    def _format_sectors_for_prompt(self, sectors: list) -> str:
        """格式化板块数据用于 prompt。"""
        if not sectors:
            return "无数据"

        return ", ".join([
            f"{s.get('name', '')}({'+' if s.get('change', 0) >= 0 else ''}{s.get('change', 0)*100:.2f}%)"
            for s in sectors
        ])

    def _format_stocks_for_prompt(self, stocks: list) -> str:
        """格式化个股数据用于 prompt。"""
        if not stocks:
            return "无数据"

        return ", ".join([
            f"{s.get('name', '')}({s.get('code', '')})"
            for s in stocks
        ])

    def _format_articles_for_prompt(self, articles: list) -> str:
        """格式化文章数据用于 prompt。"""
        if not articles:
            return "无相关新闻"

        lines = []
        for i, a in enumerate(articles, 1):
            title = a.get("title", "")
            summary = a.get("summary", "")[:200] if a.get("summary") else ""
            lines.append(f"{i}. {title}")
            if summary:
                lines.append(f"   摘要：{summary}...")

        return "\n".join(lines)
