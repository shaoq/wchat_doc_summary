"""AI 处理服务模块 - 提供文章摘要、关键词提取、分类等功能。"""

import asyncio
import logging
import re
from collections import Counter
from collections.abc import Callable
from typing import Any
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

# 板块趋势模板路径
SECTOR_TREND_TEMPLATE_PATH = Path("templates/sector_trend_summary.md")
SECTOR_TREND_MAX_TOKENS = 2500

# 分组趋势模板路径
SECTOR_GROUP_TREND_TEMPLATE_PATH = Path("templates/sector_group_trend_summary.md")
SECTOR_GROUP_TREND_MAX_TOKENS = 3000


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

        # 内容安全过滤相关：仅针对政治敏感词脱敏
        self._sensitive_patterns = [
            # 政治人物
            (re.compile(r"(习近平|李克强|王岐山|胡锦涛|江泽民|温家宝|朱镕基|魏凤和|李尚福)", re.IGNORECASE), "***"),
            # 政治组织/事件
            (re.compile(r"(中共|共产党|国民党|民进党|政治局|中纪委|政法委|六四|天安门|法轮功)", re.IGNORECASE), "***"),
            # 分离主义
            (re.compile(r"(台湾独立|藏独|疆独|港独|台独)", re.IGNORECASE), "***"),
            # 高级别政治动作
            (re.compile(r"(落马|双规|巡视组|查处|反腐风暴)", re.IGNORECASE), "***"),
            # 军事/司法案件（匹配"XX案"模式中的军事/政治人物）
            (re.compile(r"(军事法院|死刑缓期|受贿案.*宣判|一审宣判.*案)", re.IGNORECASE), "***"),
        ]

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

    def _sanitize_prompt(self, prompt: str) -> str:
        """对 prompt 进行去敏感化处理，降低触发内容安全审查的概率。

        策略：
        1. 正则替换已知敏感词
        2. 裁剪过长的新闻/电报原文（保留标题，截断正文）
        3. 移除可能包含敏感内容的新闻条目（标题命中敏感词时整条移除）

        Args:
            prompt: 原始 prompt

        Returns:
            脱敏后的 prompt
        """
        result = prompt

        # 第一步：逐行处理，移除标题命中敏感词的新闻/电报条目
        lines = result.split("\n")
        cleaned_lines = []
        skip_next_summary = False
        for line in lines:
            # 检查该行是否命中敏感词
            is_sensitive = False
            for pattern, _ in self._sensitive_patterns:
                if pattern.search(line):
                    is_sensitive = True
                    break

            if is_sensitive:
                # 如果是标题行（以数字. 或 - 开头），标记跳过后续摘要行
                if re.match(r"^\s*(\d+\.|-)", line):
                    skip_next_summary = True
                    continue
                # 其他命中行直接移除
                continue

            if skip_next_summary and line.strip().startswith("摘要："):
                skip_next_summary = False
                continue

            skip_next_summary = False
            cleaned_lines.append(line)

        result = "\n".join(cleaned_lines)

        # 第二步：对剩余内容做敏感词替换
        for pattern, replacement in self._sensitive_patterns:
            result = pattern.sub(replacement, result)

        return result

    def _is_content_safety_error(self, error: Exception) -> bool:
        """判断是否为内容安全审查错误。"""
        error_str = str(error)
        return "'1301'" in error_str or "敏感内容" in error_str or "不安全" in error_str

    async def _call_api(
        self, prompt: str, max_tokens: int = 500, *, stage: str = "",
        retry_callback: Any | None = None,
    ) -> str:
        """调用 LLM API。

        当遇到内容安全审查错误 (1301) 时，自动对 prompt 做去敏感化处理后重试。

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数
            stage: 调用阶段标识（如 "initial-summary"、"strategy-enhancement"），
                   用于日志中区分失败来源
            retry_callback: 重试事件回调（接收 dict）

        Returns:
            LLM 响应文本
        """
        def _safe_base_url_host() -> str:
            """提取 base_url 的 host 部分（不暴露完整 URL）。"""
            base_url = self.settings.llm_base_url or ""
            if not base_url:
                return ""
            try:
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                return parsed.hostname or ""
            except Exception:
                return ""

        async with self._request_semaphore:
            await asyncio.sleep(self._request_interval)

            current_prompt = prompt
            sanitized = False
            stage_label = f" [{stage}]" if stage else ""

            for attempt in range(self.settings.max_retries + 1):
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": current_prompt}],
                    )

                    content = response.content[0]
                    return content.text if hasattr(content, "text") else str(content)

                except Exception as e:
                    is_safety = self._is_content_safety_error(e)

                    if is_safety and not sanitized:
                        # 首次遇到安全错误：去敏感化后重试
                        logger.warning(
                            "触发内容安全审查，自动去敏感化后重试%s", stage_label
                        )
                        current_prompt = self._sanitize_prompt(prompt)
                        sanitized = True
                        await asyncio.sleep(1)
                        continue

                    if is_safety and sanitized:
                        # 已经去敏后仍触发安全审查：不再重复去敏
                        logger.error(
                            "内容安全审查在去敏后仍然失败%s，保留原始错误",
                            stage_label,
                        )
                        raise

                    if attempt < self.settings.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(
                            "API 调用失败%s (尝试 %d/%d)，%d秒后重试: %s",
                            stage_label,
                            attempt + 1,
                            self.settings.max_retries + 1,
                            wait_time,
                            e,
                        )
                        # 发送安全重试诊断
                        if retry_callback is not None:
                            retry_callback({
                                "type": "api_retry",
                                "stage": stage,
                                "attempt": attempt + 1,
                                "max_attempts": self.settings.max_retries + 1,
                                "retry_delay": wait_time,
                                "error": str(e)[:200],
                                "provider": "anthropic",
                                "model": self.model,
                                "base_url_host": _safe_base_url_host(),
                                "exception_type": type(e).__name__,
                            })
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error("API 调用最终失败%s: %s", stage_label, e)
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
        global_market_context: dict | None = None,
    ) -> str:
        """生成市场总结。

        Args:
            trade_date: 交易日期 (YYYY-MM-DD)
            market_data: 行情数据（指数、板块、个股等）
            articles: 相关文章列表
            telegraphs: 财联社重要电报列表（可选）
            watch_items: 财联社看盘数据列表（可选）
            global_market_context: 海外市场上下文（可选）

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

        # 格式化个股（展示层裁剪：最多 15 只，数据层保留全量）
        limit_up_stocks = self._format_stocks_for_prompt(limit_up[:15])

        # 涨停股来源标记
        limit_up_quality = market_data.get("limit_up_quality", {})
        source_type = limit_up_quality.get("source_type", "")
        if source_type == "approximate_candidates":
            limit_up_stocks = limit_up_stocks + "\n(注: 涨停池数据为近似候选集，非正式涨停池)"

        # 格式化文章
        articles_text = self._format_articles_for_prompt(articles[:10])

        # 格式化电报
        telegraphs_text = self._format_telegraphs_for_prompt(telegraphs[:30] if telegraphs else [])

        # 格式化看盘数据
        watch_items_text = self._format_watch_items_for_prompt(watch_items[:50] if watch_items else [])

        if global_market_context is None:
            global_market_context = market_data.get("global_market_context")
        global_market_context_text = self._format_global_market_context_for_prompt(global_market_context)

        # 构建数据缺口提示
        breadth_quality = market_data.get("breadth_quality", {})
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
            stats_quality=breadth_quality.get("statistics"),
            limit_up_quality=market_data.get("limit_up_quality"),
            global_market_context=global_market_context,
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
            global_market_context=global_market_context_text,
            articles=articles_text,
            data_gaps=data_gaps,
        )

        # 调用 API
        logger.info("开始生成市场总结: %s", trade_date)
        summary = await self._call_api(
            prompt, max_tokens=MARKET_SUMMARY_MAX_TOKENS, stage="initial-summary"
        )

        if self._strategy_section_needs_enhancement(summary):
            logger.info("检测到后续策略建议与风险提示内容偏弱，开始二次增强")
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
                global_market_context=global_market_context,
                data_gaps=data_gaps,
            )
            try:
                enhanced_strategy = await self._call_api(
                    strategy_prompt,
                    max_tokens=MARKET_STRATEGY_ENHANCEMENT_MAX_TOKENS,
                    stage="strategy-enhancement",
                )
                summary = self._merge_strategy_section(summary, enhanced_strategy)
            except Exception as e:
                if self._is_content_safety_error(e):
                    logger.warning(
                        "策略增强因内容安全审查失败，保留首轮总结 [strategy-enhancement]"
                    )
                else:
                    logger.warning(
                        "策略增强调用失败，保留首轮总结 [strategy-enhancement]: %s", e
                    )

        logger.info("市场总结生成完成")

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
        global_market_context: dict | None,
        data_gaps: str,
    ) -> str:
        """构建第六节后续策略增强 prompt。

        使用结构化策略证据和简洁前五节摘要代替完整 prose，
        同时过滤电报/文章标题中的敏感内容。
        """
        prior_context = self._build_prior_context_digest(summary)
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
            global_market_context=global_market_context,
            data_gaps=data_gaps,
        )

        return f"""你正在补写并强化一份 A 股市场总结的最后一节。交易日期：{trade_date}

前五节核心结论摘要（请保持判断口径一致）：
{prior_context}

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
5. 不得出现"继续关注""值得留意""主线清晰"等无证据支撑的空话。
6. 必须明确策略态度是"看多 / 观察 / 回避"中的哪一种，不能模糊。
7. 若某类证据不足，必须写成"观察 / 等待验证 / 暂不下判断"，不能强行给出进攻性结论。
8. 主线与板块策略要回答持续性、分歧回流预期、跟风与主线的区分。
9. 个股与情绪策略要回答高标带动性、涨停溢价、炸板反馈、接力还是等待。
10. 关键消息与事件策略要回答隔夜发酵可能、日内刺激还是中期催化，以及确认信号。

现在只输出完整的第六节正文："""

    def _build_prior_context_digest(self, summary: str) -> str:
        """从前五节总结中提取各节核心结论的简洁摘要。

        代替将完整 prose 传入策略增强 prompt，仅保留各节的关键结论要点。

        Args:
            summary: 完整的 market summary 文本

        Returns:
            各节核心结论的简洁摘要文本
        """
        summary_without_strategy = self._remove_strategy_section(summary).strip()
        if not summary_without_strategy:
            return "无前五节内容"

        section_headers = [
            ("一、市场概览", "市场概览"),
            ("二、主线与轮动", "主线与轮动"),
            ("三、个股与情绪", "个股与情绪"),
            ("四、关键信息催化", "关键信息催化"),
            ("五、明日观察清单", "明日观察清单"),
        ]

        lines: list[str] = []
        for marker, label in section_headers:
            # 提取该节的第一行非空内容作为核心结论
            section_text = self._extract_section_text(
                summary_without_strategy, marker
            )
            if section_text:
                # 取前 120 字符作为简洁摘要
                core = section_text.strip().replace("\n", " ")[:120]
                lines.append(f"- {label}: {core}")
            else:
                lines.append(f"- {label}: 无")

        return "\n".join(lines)

    def _extract_section_text(self, text: str, section_marker: str) -> str:
        """从文本中提取指定章节的内容。

        Args:
            text: 完整文本
            section_marker: 章节标记（如 "一、市场概览"）

        Returns:
            该章节的文本内容
        """
        pattern = rf"(?ms)^##\s*{re.escape(section_marker)}\s*\n(.*?)(?=^##\s|\Z)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

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
        global_market_context: dict | None,
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
            f"- 海外市场上下文: {self._format_global_market_context_for_prompt(global_market_context)}",
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
            safe_titles = self._filter_safe_titles(
                [t.get("title", "").strip() for t in telegraphs[:6]]
            )
            if safe_titles:
                lines.append(f"- 财联社电报关键标题: {'；'.join(safe_titles)}")
            else:
                lines.append("- 财联社电报关键标题: 事件标题证据不可用，仅使用结构化信号")

        if articles:
            safe_article_titles = self._filter_safe_titles(
                [a.get("title", "").strip() for a in articles[:5]]
            )
            if safe_article_titles:
                lines.append(f"- 文章观点标题: {'；'.join(safe_article_titles)}")
            else:
                lines.append("- 文章观点标题: 文章标题证据不可用，仅使用结构化信号")

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

    def _filter_safe_titles(self, titles: list[str]) -> list[str]:
        """过滤掉命中敏感词的标题，返回安全标题列表。

        Args:
            titles: 原始标题列表

        Returns:
            过滤后的安全标题列表
        """
        safe: list[str] = []
        for title in titles:
            if not title:
                continue
            is_sensitive = any(
                pattern.search(title) for pattern, _ in self._sensitive_patterns
            )
            if not is_sensitive:
                safe.append(title)
        return safe

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
        stats_quality: dict | None = None,
        limit_up_quality: dict | None = None,
        global_market_context: dict | None = None,
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
            stats_quality: 涨跌统计质量元数据
            limit_up_quality: 涨停股来源质量元数据
            global_market_context: 海外市场上下文

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
        elif stats_quality and stats_quality.get("status") == "near-complete":
            actual = stats_quality.get("actual_count", 0)
            expected = stats_quality.get("expected_count", 0)
            gaps.append(f"涨跌统计近完整 (样本 {actual}/{expected})，轻微缺失")
        if not top_sectors and not bottom_sectors:
            gaps.append("板块强弱数据缺失")
        if not limit_up:
            gaps.append("涨停个股数据缺失")
        elif limit_up_quality and limit_up_quality.get("source_type") == "approximate_candidates":
            gaps.append("涨停个股为近似候选集（非正式涨停池），可能含未封板个股")
        if not telegraphs:
            gaps.append("财联社电报数据缺失")
        if not watch_items:
            gaps.append("盘中看盘数据缺失")
        if not articles:
            gaps.append("文章观点数据缺失")
        if not global_market_context:
            gaps.append("海外市场上下文缺失")
        elif isinstance(global_market_context, dict):
            context_status = global_market_context.get("status")
            source_attempts = global_market_context.get("source_attempts", [])
            if context_status == "partial":
                gaps.append("海外市场上下文部分缺失，请勿补全未知海外信号")
            elif context_status != "ok":
                message = global_market_context.get("message", "海外市场上下文不可用")
                # 使用结构化失败类型生成更精确的缺口提示
                failure_hint = ""
                if source_attempts:
                    last_attempt = source_attempts[-1]
                    failure_type = last_attempt.get("failure_type", "")
                    if failure_type == "unauthorized":
                        failure_hint = "（主源被拒绝访问）"
                    elif failure_type == "rate_limited":
                        failure_hint = "（主源被限流）"
                    elif failure_type == "network_error":
                        failure_hint = "（网络错误）"
                gaps.append(f"{message}{failure_hint}，不得臆测隔夜美股表现")
        else:
            gaps.append("海外市场上下文格式异常，不得臆测隔夜美股表现")

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

    def _format_global_market_context_for_prompt(self, context: dict | None) -> str:
        """格式化海外市场上下文用于 prompt。"""
        if not context:
            return "无海外市场上下文。不得臆测隔夜美股走势或海外风险偏好。"

        status = context.get("status", "error")
        us_market = context.get("us_market", {}) if isinstance(context.get("us_market"), dict) else {}
        session = context.get("session") or us_market.get("session") or "未知"
        as_of = context.get("as_of") or us_market.get("as_of") or "未知"
        source = context.get("source") or us_market.get("source") or "未知"
        degraded = context.get("degraded", False)
        source_attempts = context.get("source_attempts", [])

        if status not in ("ok", "partial"):
            message = context.get("message", "海外市场上下文不可用")
            # 提取结构化失败类型
            failure_hint = ""
            if source_attempts:
                last_attempt = source_attempts[-1]
                failure_type = last_attempt.get("failure_type", "")
                if failure_type == "unauthorized":
                    failure_hint = "（主源被拒绝访问）"
                elif failure_type == "rate_limited":
                    failure_hint = "（主源被限流）"
                elif failure_type == "empty":
                    failure_hint = "（主源返回空数据）"
            return f"{message}{failure_hint}。不得臆测隔夜美股走势或海外风险偏好。"

        source_label = f"{source} (fallback)" if degraded else source
        lines = [
            f"状态：{status}；交易阶段：{session}；行情时间：{as_of}；来源：{source_label}",
        ]

        indices = us_market.get("indices", []) if isinstance(us_market.get("indices"), list) else []
        if indices:
            lines.append("美股指数：")
            for item in indices[:3]:
                if not isinstance(item, dict):
                    continue
                change = item.get("change_pct")
                sign = "+" if isinstance(change, (int, float)) and change >= 0 else ""
                change_text = f"{sign}{change * 100:.2f}%" if isinstance(change, (int, float)) else "N/A"
                lines.append(f"- {item.get('name', item.get('symbol', ''))}: {item.get('price', 'N/A')} ({change_text})")
        else:
            lines.append("美股指数：缺失")

        risk_signals = us_market.get("risk_signals", {}) if isinstance(us_market.get("risk_signals"), dict) else {}
        if risk_signals:
            parts = []
            for key, item in risk_signals.items():
                if not isinstance(item, dict):
                    continue
                name = item.get("name", key)
                value = item.get("value", "N/A")
                if "change_bp" in item:
                    parts.append(f"{name} {value} ({item['change_bp']:+.2f}bp)")
                elif "change_pct" in item and isinstance(item["change_pct"], (int, float)):
                    parts.append(f"{name} {value} ({item['change_pct'] * 100:+.2f}%)")
                else:
                    parts.append(f"{name} {value}")
            lines.append("风险信号：" + "；".join(parts))
        else:
            lines.append("风险信号：缺失")

        leaders = us_market.get("leaders", []) if isinstance(us_market.get("leaders"), list) else []
        leader_parts = []
        for item in leaders[:5]:
            if not isinstance(item, dict):
                continue
            change = item.get("change_pct")
            change_text = f"{change * 100:+.2f}%" if isinstance(change, (int, float)) else "N/A"
            leader_parts.append(f"{item.get('name', item.get('symbol', ''))} {change_text}")
        if leader_parts:
            lines.append("行业/龙头代理：" + "；".join(leader_parts))

        if status == "partial":
            message = context.get("message", "海外市场上下文部分缺失")
            lines.append(f"注意：{message}。只能使用已给出的海外信号，不得补全未知走势。")

        if degraded:
            lines.append("注意：主源失败后通过 fallback 获取数据，时效性可能受影响。")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 板块趋势总结
    # ------------------------------------------------------------------

    async def generate_sector_trend_summary(
        self,
        sector_name: str,
        evidence: dict,
        previous_summary: dict | None = None,
        end_date: str = "",
        window_days: int = 10,
        retry_callback: Any | None = None,
    ) -> tuple[str, dict[str, str]]:
        """生成板块趋势跟踪总结。

        Args:
            sector_name: 板块名称
            evidence: 证据数据（来自 SectorTrendAnalyzer.collect_sector_evidence）
            previous_summary: 上次总结（可选）
            end_date: 结束日期
            window_days: 回看窗口天数

        Returns:
            (报告内容, 结构化标签字典)
        """
        # 加载模板
        template = self._load_sector_trend_template()

        # 格式化行情表现
        market_appearances = self._format_sector_market_appearances(
            evidence.get("market_appearances", []),
        )

        # 格式化看盘提及
        cls_watch_mentions = self._format_sector_cls_watch(
            evidence.get("cls_watch_mentions", []),
        )

        # 格式化电报提及
        cls_telegraph_mentions = self._format_sector_cls_telegraphs(
            evidence.get("cls_telegraph_mentions", []),
        )

        # 证据充分性
        is_sparse = evidence.get("is_sparse", True)
        total_count = evidence.get("total_evidence_count", 0)
        if is_sparse:
            evidence_sufficiency = f"⚠️ 证据不足（仅 {total_count} 条记录），趋势判断将降级为观察模式"
        else:
            evidence_sufficiency = f"✓ 证据充分（共 {total_count} 条记录）"

        # 数据缺口
        data_gaps = self._build_sector_data_gaps(evidence)

        # 上次总结章节
        if previous_summary:
            previous_summary_section = (
                f"\n- **上次更新日期**: {previous_summary.get('end_date', 'N/A')}"
                f"\n- **上次趋势状态**: {previous_summary.get('trend_status', 'N/A')}"
                f"\n- **上次强度**: {previous_summary.get('strength_level', 'N/A')}"
                f"\n- **上次操作倾向**: {previous_summary.get('action_bias', 'N/A')}"
                f"\n- **上次研判**: {previous_summary.get('judgement', 'N/A')}"
            )
            change_section_instruction = (
                "对比上次更新的趋势状态，明确描述本次相比上次的变化方向。"
                "例如：由'低位启动'转为'主线延续'，或由'主线延续'转为'分歧中继'。"
            )
        else:
            previous_summary_section = "\n- **首次跟踪建档**"
            change_section_instruction = (
                "这是该板块的首次跟踪建档，不需要描述相比上次的变化。"
                "改为描述本次建档的背景和初始状态判断。"
            )

        # 构建提示词
        prompt = template.format(
            sector_name=sector_name,
            end_date=end_date,
            window_days=window_days,
            previous_summary_section=previous_summary_section,
            market_appearances=market_appearances,
            cls_watch_mentions=cls_watch_mentions,
            cls_telegraph_mentions=cls_telegraph_mentions,
            evidence_sufficiency=evidence_sufficiency,
            data_gaps=data_gaps,
            change_section_instruction=change_section_instruction,
        )

        # 调用 API
        logger.info("开始生成板块趋势总结: %s (%s)", sector_name, end_date)
        content = await self._call_api(
            prompt, max_tokens=SECTOR_TREND_MAX_TOKENS, stage="sector-trend",
            retry_callback=retry_callback,
        )

        # 提取结构化标签
        labels = self._extract_sector_trend_labels(content)
        raw_stage = labels["trend_status"]

        # 阶段验证降级
        validated_stage = self._validate_sector_stage_post_extract(
            raw_stage,
            evidence=evidence,
            previous_summary=previous_summary,
        )
        evidence["raw_label"] = raw_stage
        evidence["final_label"] = validated_stage
        evidence["validation_adjusted"] = validated_stage != raw_stage
        if validated_stage != raw_stage:
            logger.info(
                "板块趋势阶段降级: %s → %s (%s)",
                raw_stage, validated_stage, sector_name,
            )
            labels["trend_status"] = validated_stage

        content = self._sync_structured_labels(content, labels)
        return content, labels

    def _load_sector_trend_template(self) -> str:
        """加载板块趋势总结模板。"""
        if not SECTOR_TREND_TEMPLATE_PATH.exists():
            raise FileNotFoundError(
                f"板块趋势模板文件不存在: {SECTOR_TREND_TEMPLATE_PATH}"
            )
        return SECTOR_TREND_TEMPLATE_PATH.read_text(encoding="utf-8")

    def _format_sector_market_appearances(
        self, appearances: list[dict],
    ) -> str:
        """格式化板块行情表现记录。"""
        if not appearances:
            return "无近期行情强弱榜记录"

        lines = []
        for item in appearances:
            trade_date = item.get("trade_date", "N/A")
            change_pct = item.get("change_pct")
            amount = item.get("amount")
            main_inflow = item.get("main_inflow")

            parts = [f"日期: {trade_date}"]
            if change_pct is not None:
                sign = "+" if change_pct >= 0 else ""
                parts.append(f"涨跌幅: {sign}{change_pct:.2f}%")
            if amount is not None:
                parts.append(f"成交额: {amount:.1f}亿")
            if main_inflow is not None:
                parts.append(f"主力净流入: {main_inflow:.1f}亿")

            lines.append("- " + " | ".join(parts))

        return "\n".join(lines)

    def _format_sector_cls_watch(self, mentions: list[dict]) -> str:
        """格式化板块看盘数据提及。"""
        if not mentions:
            return "无看盘数据提及"

        lines = []
        for item in mentions[:20]:
            time_str = item.get("publish_time", "")
            title = item.get("title", "")
            content = (item.get("content") or "")[:150]
            stocks = item.get("stocks", [])

            line = f"- [{time_str}] {title}"
            if content:
                line += f": {content}"
            if stocks:
                line += f" [个股: {', '.join(stocks[:3])}]"
            lines.append(line)

        return "\n".join(lines)

    def _format_sector_cls_telegraphs(self, mentions: list[dict]) -> str:
        """格式化板块电报提及。"""
        if not mentions:
            return "无电报数据提及"

        lines = []
        for item in mentions[:20]:
            time_str = item.get("publish_time", "")
            level = item.get("level", "")
            title = item.get("title", "")
            content = (item.get("content") or "")[:150]

            prefix = f"- [{time_str}]"
            if level:
                prefix += f" {level}级"

            line = f"{prefix} {title}"
            if content:
                line += f": {content}"
            lines.append(line)

        return "\n".join(lines)

    def _build_sector_data_gaps(self, evidence: dict) -> str:
        """构建板块数据缺口提示。"""
        gaps: list[str] = []

        if not evidence.get("market_appearances"):
            gaps.append("行情强弱榜记录缺失")
        if not evidence.get("cls_watch_mentions"):
            gaps.append("看盘数据提及缺失")
        if not evidence.get("cls_telegraph_mentions"):
            gaps.append("电报数据提及缺失")

        if not gaps:
            return "无"

        return "⚠️ 以下证据组数据不足，请在生成时进入观察模式：\n" + "\n".join(
            f"- {gap}" for gap in gaps
        )

    def _extract_sector_trend_labels(self, content: str) -> dict[str, str]:
        """从报告内容中提取结构化标签。"""
        labels: dict[str, str] = {
            "trend_status": "暂无趋势",
            "strength_level": "弱",
            "action_bias": "观察",
            "judgement": "",
        }

        valid_trend_statuses = {
            "主线加强", "主线延续", "分歧中继", "低位启动",
            "轮动补涨", "短线脉冲", "高位退潮", "暂无趋势",
        }
        valid_strength = {"强", "中", "弱"}
        valid_actions = {"跟踪", "观察", "回避"}

        for line in content.split("\n"):
            line_stripped = line.strip().lower()

            if line_stripped.startswith("trend_status:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_trend_statuses:
                    labels["trend_status"] = value
            elif line_stripped.startswith("strength_level:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_strength:
                    labels["strength_level"] = value
            elif line_stripped.startswith("action_bias:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_actions:
                    labels["action_bias"] = value
            elif line_stripped.startswith("judgement:"):
                labels["judgement"] = line.split(":", 1)[1].strip()

        return labels

    # ------------------------------------------------------------------
    # 分组趋势总结
    # ------------------------------------------------------------------

    async def generate_sector_group_trend_summary(
        self,
        group_name: str,
        evidence: dict,
        member_freshness: list[dict],
        end_date: str = "",
        window_days: int = 10,
        retry_callback: Any | None = None,
    ) -> tuple[str, dict[str, str]]:
        """生成分组趋势跟踪总结。

        Args:
            group_name: 分组名称
            evidence: 组级证据数据
            member_freshness: 成员新鲜度列表
            end_date: 结束日期
            window_days: 回看窗口天数

        Returns:
            (报告内容, 结构化标签字典)
        """
        template = self._load_sector_group_trend_template()

        # 格式化成员报告
        member_reports = self._format_group_member_reports(
            evidence.get("member_summaries", []),
        )

        # 格式化成员新鲜度
        member_freshness_text = self._format_member_freshness(member_freshness)

        # 数据缺口
        data_gaps = self._build_group_data_gaps(evidence, member_freshness)

        prompt = template.format(
            group_name=group_name,
            end_date=end_date,
            window_days=window_days,
            member_count=evidence.get("member_count", 0),
            member_reports=member_reports,
            member_freshness=member_freshness_text,
            data_gaps=data_gaps,
        )

        logger.info("开始生成分组趋势总结: %s (%s)", group_name, end_date)
        content = await self._call_api(
            prompt, max_tokens=SECTOR_GROUP_TREND_MAX_TOKENS, stage="sector-group-trend",
            retry_callback=retry_callback,
        )

        labels = self._extract_sector_group_trend_labels(content)
        raw_stage = labels["trend_status"]

        # 阶段验证降级
        validated_stage = self._validate_group_stage_post_extract(
            raw_stage,
            evidence=evidence,
            member_freshness=member_freshness,
        )
        evidence["raw_label"] = raw_stage
        evidence["final_label"] = validated_stage
        evidence["validation_adjusted"] = validated_stage != raw_stage
        if validated_stage != raw_stage:
            logger.info(
                "分组趋势阶段降级: %s → %s (%s)",
                raw_stage, validated_stage, group_name,
            )
            labels["trend_status"] = validated_stage

        content = self._sync_structured_labels(content, labels)
        return content, labels

    def _sync_structured_labels(
        self,
        content: str,
        labels: dict[str, str],
    ) -> str:
        """把最终验证后的结构化标签同步回 Markdown 内容。"""
        final_lines = {
            "trend_status": f"trend_status: {labels.get('trend_status', '暂无趋势')}",
            "strength_level": f"strength_level: {labels.get('strength_level', '弱')}",
            "action_bias": f"action_bias: {labels.get('action_bias', '观察')}",
            "judgement": f"judgement: {labels.get('judgement', '')}",
        }

        synced = content
        for key, line in final_lines.items():
            pattern = re.compile(rf"(?im)^\s*{key}\s*:\s*.*$")
            if pattern.search(synced):
                synced = pattern.sub(line, synced)
            else:
                synced = synced.rstrip() + f"\n{line}\n"
        return synced

    def _load_sector_group_trend_template(self) -> str:
        """加载分组趋势总结模板。"""
        if not SECTOR_GROUP_TREND_TEMPLATE_PATH.exists():
            raise FileNotFoundError(
                f"分组趋势模板文件不存在: {SECTOR_GROUP_TREND_TEMPLATE_PATH}"
            )
        return SECTOR_GROUP_TREND_TEMPLATE_PATH.read_text(encoding="utf-8")

    def _format_group_member_reports(
        self, member_summaries: list[dict],
    ) -> str:
        """格式化成员板块报告。"""
        if not member_summaries:
            return "无成员板块报告"

        lines = []
        for ms in member_summaries:
            name = ms.get("sector_name", "未知")
            status = ms.get("sector_status", "-")
            relation = ms.get("relation_type", "-")
            has_summary = ms.get("has_summary", False)

            header = f"### {name} (关系: {relation}, 状态: {status})"
            lines.append(header)

            if not has_summary:
                lines.append("⚠️ 无趋势总结报告\n")
                continue

            summary_date = ms.get("summary_date", "-")
            trend = ms.get("trend_status", "-")
            strength = ms.get("strength_level", "-")
            bias = ms.get("action_bias", "-")
            judgement = ms.get("judgement", "-")

            lines.append(f"- 报告日期: {summary_date}")
            lines.append(f"- 趋势状态: {trend}")
            lines.append(f"- 强度: {strength}")
            lines.append(f"- 倾向: {bias}")
            lines.append(f"- 研判: {judgement}")

            content = ms.get("summary_content", "")
            if content:
                # 截取核心内容，避免过长
                truncated = content[:800]
                if len(content) > 800:
                    truncated += "..."
                lines.append(f"\n{truncated}\n")

        return "\n".join(lines)

    def _format_member_freshness(
        self, freshness_list: list[dict],
    ) -> str:
        """格式化成员新鲜度信息。"""
        if not freshness_list:
            return "无成员新鲜度数据"

        lines = []
        for f in freshness_list:
            name = f.get("sector_name", "未知")
            status = f.get("sector_status", "-")
            relation = f.get("relation_type", "-")
            is_candidate = f.get("is_candidate", False)
            is_stale = f.get("is_stale", False)
            is_missing = f.get("is_missing", False)
            latest_date = f.get("latest_summary_date", "-")
            target_date = f.get("target_date", "-")

            flags = []
            if is_candidate:
                flags.append("candidate(不参与默认刷新)")
            if is_stale:
                flags.append(f"过期(最新报告{latest_date}，目标{target_date})")
            if is_missing:
                flags.append("缺少报告")
            if not flags:
                flags.append(f"最新(报告日期{latest_date})")

            lines.append(f"- **{name}** ({relation}, {status}): {'; '.join(flags)}")

        return "\n".join(lines)

    def _build_group_data_gaps(
        self,
        evidence: dict,
        member_freshness: list[dict],
    ) -> str:
        """构建分组数据缺口提示。"""
        gaps: list[str] = []

        member_summaries = evidence.get("member_summaries", [])
        total = len(member_summaries)
        with_summary = sum(1 for m in member_summaries if m.get("has_summary"))
        missing = total - with_summary

        if missing == total:
            gaps.append("所有成员板块缺少趋势总结报告")
        elif missing > 0:
            gaps.append(f"{missing}/{total} 个成员板块缺少趋势总结报告")

        stale_count = sum(1 for f in member_freshness if f.get("is_stale"))
        if stale_count:
            gaps.append(f"{stale_count} 个成员报告已过期（非目标日期）")

        candidate_count = sum(1 for f in member_freshness if f.get("is_candidate"))
        if candidate_count:
            gaps.append(f"{candidate_count} 个成员为 candidate 状态，默认不参与跟踪分析")

        if not gaps:
            return "无"

        return "⚠️ 以下证据组数据不足，请在生成时进入观察模式：\n" + "\n".join(
            f"- {gap}" for gap in gaps
        )

    def _extract_sector_group_trend_labels(self, content: str) -> dict[str, str]:
        """从分组报告内容中提取结构化标签。"""
        labels: dict[str, str] = {
            "trend_status": "暂无趋势",
            "strength_level": "弱",
            "action_bias": "观察",
            "judgement": "",
        }

        valid_trend_statuses = {
            "主线共振", "主线扩散", "轮动分化", "低位启动",
            "补涨蔓延", "短线脉冲", "高位退潮", "暂无趋势",
        }
        valid_strength = {"强", "中", "弱"}
        valid_actions = {"跟踪", "观察", "回避"}

        for line in content.split("\n"):
            line_stripped = line.strip().lower()

            if line_stripped.startswith("trend_status:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_trend_statuses:
                    labels["trend_status"] = value
            elif line_stripped.startswith("strength_level:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_strength:
                    labels["strength_level"] = value
            elif line_stripped.startswith("action_bias:"):
                value = line.split(":", 1)[1].strip()
                if value in valid_actions:
                    labels["action_bias"] = value
            elif line_stripped.startswith("judgement:"):
                labels["judgement"] = line.split(":", 1)[1].strip()

        return labels

    def _validate_sector_stage_post_extract(
        self,
        stage: str,
        *,
        evidence: dict,
        previous_summary: dict | None = None,
    ) -> str:
        """对板块 AI 输出阶段执行验证降级。"""
        from src.services.trend_stage_taxonomy import validate_sector_stage

        is_sparse = evidence.get("is_sparse", True)
        has_market = bool(evidence.get("market_appearances"))
        has_prior = previous_summary is not None
        prior_stage = (
            previous_summary.get("trend_status") if previous_summary else None
        )
        is_first_report = not has_prior

        market_role = evidence.get("market_evidence_role", "no_market")
        has_high_confidence_alias = bool(evidence.get("high_confidence_aliases"))
        has_proxy_market = bool(evidence.get("proxy_market_appearances")) or bool(
            evidence.get("has_proxy_market_evidence")
        )
        has_fresh_info = bool(
            evidence.get("cls_watch_mentions") or evidence.get("cls_telegraph_mentions")
        )

        # 多信号新鲜证据：有直接/别名行情 + 至少一个信息源
        has_multi_signal = (
            (has_market or market_role == "alias_market")
            and has_fresh_info
        )

        return validate_sector_stage(
            stage,
            is_sparse=is_sparse,
            has_market_evidence=has_market,
            has_prior=has_prior,
            prior_stage=prior_stage,
            is_first_report=is_first_report,
            has_multi_signal_fresh=has_multi_signal,
            market_evidence_role=market_role,
            has_high_confidence_alias=has_high_confidence_alias,
            has_proxy_market_with_confirmation=has_proxy_market and has_fresh_info,
            has_fresh_watch_or_telegraph=has_fresh_info,
        )

    def _validate_group_stage_post_extract(
        self,
        stage: str,
        *,
        evidence: dict,
        member_freshness: list[dict],
    ) -> str:
        """对分组 AI 输出阶段执行验证降级。"""
        from src.services.trend_stage_taxonomy import validate_group_stage

        # 构建成员板块状态列表
        member_summaries = evidence.get("member_summaries", [])
        member_sectors = []
        for ms in member_summaries:
            member_sectors.append({
                "sector_name": ms.get("sector_name", ""),
                "trend_status": ms.get("trend_status", ""),
                "sector_status": ms.get("sector_status", ""),
                "relation_type": ms.get("relation_type", ""),
                "is_fresh": any(
                    mf.get("sector_name") == ms.get("sector_name") and mf.get("is_fresh", False)
                    for mf in member_freshness
                ),
            })

        return validate_group_stage(
            stage,
            member_freshness=member_freshness,
            member_sectors=member_sectors,
            member_evidence_quality=evidence.get("member_evidence_quality", []),
        )
