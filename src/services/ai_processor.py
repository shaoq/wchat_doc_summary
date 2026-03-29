"""AI 处理服务模块 - 提供文章摘要、关键词提取、分类等功能。"""

import asyncio
import logging
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

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

# 市场总结模板路径
MARKET_SUMMARY_TEMPLATE_PATH = Path("templates/market_summary.md")
MARKET_SUMMARY_MAX_TOKENS = 2200
MARKET_STRATEGY_ENHANCEMENT_MAX_TOKENS = 1200


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

    def _load_market_summary_template(self) -> str:
        """加载市场总结模板。

        从 templates/market_summary.md 文件加载模板。

        Returns:
            模板内容

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if not MARKET_SUMMARY_TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"市场总结模板文件不存在: {MARKET_SUMMARY_TEMPLATE_PATH}")

        return MARKET_SUMMARY_TEMPLATE_PATH.read_text(encoding="utf-8")

    async def generate_market_summary(
        self,
        trade_date: str,
        market_data: dict,
        articles: list[dict],
        telegraphs: list[dict] | None = None,
        watch_items: list[dict] | None = None,
    ) -> str:
        """生成市场总结。

        Args:
            trade_date: 交易日期 (YYYY-MM-DD)
            market_data: 行情数据（指数、板块、个股等）
            articles: 相关文章列表
            telegraphs: 财联社重要电报列表（可选）
            watch_items: 财联社看盘数据列表（可选）

        Returns:
            市场总结文本
        """
        # 加载模板
        template = self._load_market_summary_template()

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

        # 格式化电报
        telegraphs_text = self._format_telegraphs_for_prompt(telegraphs[:30] if telegraphs else [])

        # 格式化看盘数据
        watch_items_text = self._format_watch_items_for_prompt(watch_items[:50] if watch_items else [])

        # 构建数据缺口提示
        data_gaps = self._build_data_gaps(
            indices=indices,
            volume=market_data.get("volume"),
            stats=stats,
            top_sectors=sectors.get("top_sectors", []),
            bottom_sectors=sectors.get("bottom_sectors", []),
            limit_up=limit_up,
            telegraphs=telegraphs,
            watch_items=watch_items,
            articles=articles,
        )

        # 构建提示词
        prompt = template.format(
            trade_date=trade_date,
            indices_summary=indices_summary,
            volume=volume,
            up_count=stats.get("up_count", "N/A"),
            down_count=stats.get("down_count", "N/A"),
            flat_count=stats.get("flat_count", "N/A"),
            top_sectors=top_sectors,
            bottom_sectors=bottom_sectors,
            limit_up_stocks=limit_up_stocks,
            cls_telegraphs=telegraphs_text,
            cls_watch_items=watch_items_text,
            articles=articles_text,
            data_gaps=data_gaps,
        )

        # 调用 API
        logger.info(f"开始生成市场总结: {trade_date}")
        summary = await self._call_api(prompt, max_tokens=MARKET_SUMMARY_MAX_TOKENS)

        if self._strategy_section_needs_enhancement(summary):
            logger.info("检测到“后续策略建议与风险提示”内容偏弱，开始二次增强")
            strategy_prompt = self._build_strategy_enhancement_prompt(
                trade_date=trade_date,
                summary=summary,
                indices_summary=indices_summary,
                volume=volume,
                stats=stats,
                top_sectors=sectors.get("top_sectors", []),
                bottom_sectors=sectors.get("bottom_sectors", []),
                limit_up=limit_up,
                telegraphs=telegraphs or [],
                watch_items=watch_items or [],
                articles=articles,
                data_gaps=data_gaps,
            )
            enhanced_strategy = await self._call_api(
                strategy_prompt,
                max_tokens=MARKET_STRATEGY_ENHANCEMENT_MAX_TOKENS,
            )
            summary = self._merge_strategy_section(summary, enhanced_strategy)

        logger.info(f"市场总结生成完成")

        return summary

    def _build_strategy_enhancement_prompt(
        self,
        trade_date: str,
        summary: str,
        indices_summary: str,
        volume: str,
        stats: dict,
        top_sectors: list,
        bottom_sectors: list,
        limit_up: list,
        telegraphs: list,
        watch_items: list,
        articles: list,
        data_gaps: str,
    ) -> str:
        """构建第六节后续策略增强 prompt。"""
        summary_without_strategy = self._remove_strategy_section(summary).strip()
        strategy_digest = self._build_strategy_evidence_digest(
            indices_summary=indices_summary,
            volume=volume,
            stats=stats,
            top_sectors=top_sectors,
            bottom_sectors=bottom_sectors,
            limit_up=limit_up,
            telegraphs=telegraphs,
            watch_items=watch_items,
            articles=articles,
            data_gaps=data_gaps,
        )

        return f"""你正在补写并强化一份 A 股市场总结的最后一节。交易日期：{trade_date}

现有总结前五节如下，请保持其判断口径一致，不要重复前五节内容：
{summary_without_strategy}

以下是只允许使用的策略辅助证据，请围绕这些信号展开，不要脱离证据泛化发挥：
{strategy_digest}

硬性输出要求：
1. 你只输出一个完整章节：`## 六、后续策略建议与风险提示`，不要输出其他章节、开场白或结束语。
2. 该章节下必须按固定顺序包含以下三个小节：
   - `### 6.1 主线与板块策略`
   - `### 6.2 个股与情绪策略`
   - `### 6.3 关键消息与事件策略`
3. 整个第六节至少输出 4 条策略，其中：
   - 主线与板块策略至少 2 条
   - 个股与情绪策略至少 1 条
   - 关键消息与事件策略至少 1 条
4. 每条策略都必须严格使用以下格式：
   - **观察/策略**: [具体方向、板块、个股或事件]
     - **依据**: [明确引用指数/成交额/板块/涨停/电报/看盘/文章中的具体证据]
     - **应对**: [次日触发条件、确认信号、节奏或仓位表达]
     - **风险**: [风险点、失效条件、何时放弃]
5. 不得出现“继续关注”“值得留意”“主线清晰”等无证据支撑的空话。
6. 必须明确策略态度是“看多 / 观察 / 回避”中的哪一种，不能模糊。
7. 若某类证据不足，必须写成“观察 / 等待验证 / 暂不下判断”，不能强行给出进攻性结论。
8. 主线与板块策略要回答持续性、分歧回流预期、跟风与主线的区分。
9. 个股与情绪策略要回答高标带动性、涨停溢价、炸板反馈、接力还是等待。
10. 关键消息与事件策略要回答隔夜发酵可能、日内刺激还是中期催化，以及确认信号。

现在只输出完整的第六节正文："""

    def _build_strategy_evidence_digest(
        self,
        indices_summary: str,
        volume: str,
        stats: dict,
        top_sectors: list,
        bottom_sectors: list,
        limit_up: list,
        telegraphs: list,
        watch_items: list,
        articles: list,
        data_gaps: str,
    ) -> str:
        """构建策略增强用的压缩证据摘要。"""
        lines = [
            "### 策略辅助信号",
            f"- 指数概览: {indices_summary}",
            f"- 两市成交额: {volume} 亿元",
            (
                f"- 市场宽度: 上涨 {stats.get('up_count', 'N/A')} 家，"
                f"下跌 {stats.get('down_count', 'N/A')} 家，"
                f"平盘 {stats.get('flat_count', 'N/A')} 家"
            ),
            f"- 强势板块候选: {self._format_sectors_for_prompt(top_sectors[:5])}",
            f"- 弱势板块候选: {self._format_sectors_for_prompt(bottom_sectors[:5])}",
            f"- 涨停与核心个股样本: {self._format_stocks_for_prompt(limit_up[:12])}",
        ]

        watch_sector_counter: Counter[str] = Counter()
        watch_stock_counter: Counter[str] = Counter()
        for item in watch_items[:20]:
            for sector in item.get("sectors", []) or []:
                if sector:
                    watch_sector_counter[sector] += 1
            for stock in item.get("stocks", []) or []:
                if stock:
                    watch_stock_counter[stock] += 1

        if watch_sector_counter:
            sector_summary = "、".join(
                f"{name}({count}次提及)"
                for name, count in watch_sector_counter.most_common(5)
            )
            lines.append(f"- 盘中轮动高频板块: {sector_summary}")
        else:
            lines.append("- 盘中轮动高频板块: 无明显高频板块线索")

        if watch_stock_counter:
            stock_summary = "、".join(
                f"{name}({count}次提及)"
                for name, count in watch_stock_counter.most_common(5)
            )
            lines.append(f"- 盘中高频个股: {stock_summary}")
        else:
            lines.append("- 盘中高频个股: 无明显重复提及个股")

        if telegraphs:
            telegraph_titles = "；".join(
                t.get("title", "").strip()
                for t in telegraphs[:6]
                if t.get("title", "").strip()
            )
            if telegraph_titles:
                lines.append(f"- 财联社电报关键标题: {telegraph_titles}")

        if articles:
            article_titles = "；".join(
                a.get("title", "").strip()
                for a in articles[:5]
                if a.get("title", "").strip()
            )
            if article_titles:
                lines.append(f"- 文章观点标题: {article_titles}")

        lines.append(f"- 数据缺口与降级约束: {data_gaps}")
        return "\n".join(lines)

    def _extract_strategy_section(self, summary: str) -> str | None:
        """提取第六节后续策略建议与风险提示。"""
        match = re.search(
            r"(?ms)^##\s*六、后续策略建议与风险提示\s*\n.*?(?=^##\s|\Z)",
            summary.strip(),
        )
        return match.group(0).strip() if match else None

    def _remove_strategy_section(self, summary: str) -> str:
        """移除第六节，保留前文内容。"""
        return re.sub(
            r"(?ms)\n*^##\s*六、后续策略建议与风险提示\s*\n.*?(?=^##\s|\Z)",
            "",
            summary.strip(),
        ).strip()

    def _strategy_section_needs_enhancement(self, summary: str) -> bool:
        """判断第六节是否过于简单，需要二次增强。"""
        strategy_section = self._extract_strategy_section(summary)
        if not strategy_section:
            return True

        required_subsections = [
            "### 6.1 主线与板块策略",
            "### 6.2 个股与情绪策略",
            "### 6.3 关键消息与事件策略",
        ]
        if any(subsection not in strategy_section for subsection in required_subsections):
            return True

        strategy_item_count = len(re.findall(r"(?m)^- \*\*观察/策略\*\*:", strategy_section))
        if strategy_item_count < 4:
            return True

        if len(strategy_section.strip()) < 500:
            return True

        return False

    def _normalize_strategy_section(self, strategy_section: str) -> str:
        """标准化第六节文本，确保包含章节标题。"""
        normalized = strategy_section.strip()
        if not normalized.startswith("## 六、后续策略建议与风险提示"):
            normalized = (
                "## 六、后续策略建议与风险提示\n" + normalized.lstrip("#").strip()
            )
        return normalized.strip()

    def _merge_strategy_section(self, summary: str, strategy_section: str) -> str:
        """将增强后的第六节合并回完整总结。"""
        normalized_strategy = self._normalize_strategy_section(strategy_section)

        if self._extract_strategy_section(summary):
            return re.sub(
                r"(?ms)^##\s*六、后续策略建议与风险提示\s*\n.*?(?=^##\s|\Z)",
                normalized_strategy,
                summary.strip(),
            ).strip()

        summary_without_strategy = summary.rstrip()
        if summary_without_strategy:
            return f"{summary_without_strategy}\n\n{normalized_strategy}"
        return normalized_strategy

    def _build_data_gaps(
        self,
        indices: dict,
        volume: dict | None,
        stats: dict,
        top_sectors: list,
        bottom_sectors: list,
        limit_up: list,
        telegraphs: list | None,
        watch_items: list | None,
        articles: list,
    ) -> str:
        """构建数据缺口提示文本。

        检查各证据组是否为空或明显不足，为模型提供降级依据。

        Args:
            indices: 指数数据
            volume: 成交额数据
            stats: 涨跌统计数据
            top_sectors: 涨幅板块列表
            bottom_sectors: 跌幅板块列表
            limit_up: 涨停个股列表
            telegraphs: 电报列表
            watch_items: 看盘数据列表
            articles: 文章列表

        Returns:
            数据缺口描述文本，无缺口时返回"无"
        """
        gaps: list[str] = []

        if not indices:
            gaps.append("指数行情数据缺失")
        if not volume or not volume.get("total_volume"):
            gaps.append("成交额数据缺失")
        if not stats:
            gaps.append("涨跌统计数据缺失")
        if not top_sectors and not bottom_sectors:
            gaps.append("板块强弱数据缺失")
        if not limit_up:
            gaps.append("涨停个股数据缺失")
        if not telegraphs:
            gaps.append("财联社电报数据缺失")
        if not watch_items:
            gaps.append("盘中看盘数据缺失")
        if not articles:
            gaps.append("文章观点数据缺失")

        if not gaps:
            return "无"

        return "⚠️ 以下证据组数据不足，请在生成时进入观察模式：\n" + "\n".join(
            f"- {gap}" for gap in gaps
        )

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

    def _format_telegraphs_for_prompt(self, telegraphs: list) -> str:
        """格式化财联社电报数据用于 prompt。"""
        if not telegraphs:
            return "无重要电报"

        lines = []
        for t in telegraphs:
            time_str = t.get("publish_time", "")
            title = t.get("title", "")
            content = t.get("content", "")[:150] if t.get("content") else ""

            if title and content:
                lines.append(f"- [{time_str}] {title}: {content}")
            elif title:
                lines.append(f"- [{time_str}] {title}")
            elif content:
                lines.append(f"- [{time_str}] {content}")

        return "\n".join(lines)

    def _format_watch_items_for_prompt(self, watch_items: list) -> str:
        """格式化看盘数据用于 prompt。"""
        if not watch_items:
            return "无看盘数据"

        lines = []
        for item in watch_items:
            time_str = item.get("publish_time", "")
            title = item.get("title", "")
            content = item.get("content", "")[:200] if item.get("content") else ""

            # 提取涉及的股票和板块
            stocks = item.get("stocks", [])
            sectors = item.get("sectors", [])

            extra_info = []
            if stocks:
                extra_info.append(f"个股: {', '.join(stocks[:5])}")
            if sectors:
                extra_info.append(f"板块: {', '.join(sectors[:3])}")

            extra_str = f" [{', '.join(extra_info)}]" if extra_info else ""

            if title and content:
                lines.append(f"- [{time_str}] {title}: {content}{extra_str}")
            elif title:
                lines.append(f"- [{time_str}] {title}{extra_str}")
            elif content:
                lines.append(f"- [{time_str}] {content}{extra_str}")

        return "\n".join(lines)
