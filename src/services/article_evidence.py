"""文章证据提取与缓存服务 — 为市场总结自动准备结构化公众号文章观点证据。

本服务提供:
1. 标准化文章证据 schema 与验证
2. AI 驱动的文章证据提取
3. 基于 ArticleProcessing 的证据缓存
4. 有界批量证据准备
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import select

from src.models.schema import Article, ArticleProcessing, Feed
from src.storage.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TASK_TYPE = "market_article_evidence"
MAX_CANDIDATES = 10

# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class ArticleRelevance(str, Enum):
    """文章市场相关度。"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELATED = "unrelated"


class EvidenceOutcome(str, Enum):
    """单篇文章证据准备结果。"""
    PREPARED = "prepared"       # 新提取成功
    REUSED = "reused"           # 复用缓存
    SKIPPED = "skipped"         # 跳过（低相关度等）
    FAILED = "failed"           # 提取失败
    INVALID = "invalid"         # 缓存格式无效
    FALLBACK = "fallback"       # 内容不足，降级到标题/摘要信号


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketArticleEvidence:
    """单篇文章的结构化市场观点证据。"""

    article_type: str = ""              # review / strategy / news / commentary
    relevance: str = ArticleRelevance.LOW.value
    time_role: str = ""                 # post_close_review / pre_market_strategy / intraday
    mentioned_sectors: tuple[str, ...] = ()
    mentioned_stocks: tuple[str, ...] = ()
    mainline_views: tuple[str, ...] = ()
    sentiment_view: str = ""            # bullish / bearish / neutral / mixed
    next_day_watch_items: tuple[str, ...] = ()
    risk_points: tuple[str, ...] = ()
    usable_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "article_type": self.article_type,
            "relevance": self.relevance,
            "time_role": self.time_role,
            "mentioned_sectors": list(self.mentioned_sectors),
            "mentioned_stocks": list(self.mentioned_stocks),
            "mainline_views": list(self.mainline_views),
            "sentiment_view": self.sentiment_view,
            "next_day_watch_items": list(self.next_day_watch_items),
            "risk_points": list(self.risk_points),
            "usable_summary": self.usable_summary,
        }


@dataclass(frozen=True)
class ArticleEvidenceRecord:
    """带有文章 ID 和来源信息的证据记录。"""

    article_id: int
    title: str
    evidence: MarketArticleEvidence
    outcome: EvidenceOutcome
    feed_name: str = ""
    feed_weight: int = 5
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "article_id": self.article_id,
            "title": self.title,
            "outcome": self.outcome.value,
            "feed_name": self.feed_name,
            "feed_weight": self.feed_weight,
            "provider": self.provider,
            "evidence": self.evidence.to_dict(),
        }


@dataclass
class BatchPreparationResult:
    """批量证据准备结果。"""

    records: list[ArticleEvidenceRecord] = field(default_factory=list)
    prepared: int = 0
    reused: int = 0
    skipped: int = 0
    failed: int = 0
    invalid: int = 0
    fallback: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "total": self.total,
            "prepared": self.prepared,
            "reused": self.reused,
            "skipped": self.skipped,
            "failed": self.failed,
            "invalid": self.invalid,
            "fallback": self.fallback,
            "records": [r.to_dict() for r in self.records],
        }


# ---------------------------------------------------------------------------
# Schema 验证
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = frozenset({
    "relevance", "article_type", "usable_summary",
})

ALL_FIELDS = frozenset({
    "article_type", "relevance", "time_role",
    "mentioned_sectors", "mentioned_stocks",
    "mainline_views", "sentiment_view",
    "next_day_watch_items", "risk_points",
    "usable_summary",
})

DEFAULT_EVIDENCE = {
    "article_type": "",
    "relevance": ArticleRelevance.LOW.value,
    "time_role": "",
    "mentioned_sectors": [],
    "mentioned_stocks": [],
    "mainline_views": [],
    "sentiment_view": "",
    "next_day_watch_items": [],
    "risk_points": [],
    "usable_summary": "",
}


def validate_evidence_dict(data: dict[str, Any] | None) -> MarketArticleEvidence | None:
    """验证并规范化证据字典为 MarketArticleEvidence。

    Args:
        data: 原始证据字典

    Returns:
        规范化后的证据对象，验证失败返回 None
    """
    if not data or not isinstance(data, dict):
        return None

    # 检查必填字段
    for key in REQUIRED_FIELDS:
        if key not in data:
            return None

    # 用默认值填充缺失字段
    normalized: dict[str, Any] = dict(DEFAULT_EVIDENCE)
    for key, value in data.items():
        if key in ALL_FIELDS:
            normalized[key] = value

    # 确保列表字段为列表
    for list_field in (
        "mentioned_sectors", "mentioned_stocks", "mainline_views",
        "next_day_watch_items", "risk_points",
    ):
        val = normalized.get(list_field)
        if not isinstance(val, list):
            normalized[list_field] = []

    # 验证 relevance 合法值
    valid_relevances = {r.value for r in ArticleRelevance}
    if normalized["relevance"] not in valid_relevances:
        normalized["relevance"] = ArticleRelevance.LOW.value

    return MarketArticleEvidence(
        article_type=str(normalized["article_type"]),
        relevance=str(normalized["relevance"]),
        time_role=str(normalized["time_role"]),
        mentioned_sectors=tuple(str(s) for s in normalized["mentioned_sectors"]),
        mentioned_stocks=tuple(str(s) for s in normalized["mentioned_stocks"]),
        mainline_views=tuple(str(v) for v in normalized["mainline_views"]),
        sentiment_view=str(normalized["sentiment_view"]),
        next_day_watch_items=tuple(str(w) for w in normalized["next_day_watch_items"]),
        risk_points=tuple(str(r) for r in normalized["risk_points"]),
        usable_summary=str(normalized["usable_summary"]),
    )


def parse_evidence_json(raw_json: str | None) -> MarketArticleEvidence | None:
    """解析 JSON 字符串为 MarketArticleEvidence。

    Args:
        raw_json: 原始 JSON 字符串

    Returns:
        规范化后的证据对象，解析失败返回 None
    """
    if not raw_json:
        return None

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    return validate_evidence_dict(data)


# ---------------------------------------------------------------------------
# 关键词信号
# ---------------------------------------------------------------------------

# 复盘类关键词
REVIEW_KEYWORDS = re.compile(
    r"复盘|收评|总结|回顾|盘后|盘面总结|市场回顾|行情回顾|今日市况|A股收市|收盘评论",
)

# 策略类关键词
STRATEGY_KEYWORDS = re.compile(
    r"策略|明日|预判|前瞻|布局|操作建议|投资策略|交易策略|关注方向|后市展望|隔夜观点|操盘",
)

# 主线类关键词
MAINLINE_KEYWORDS = re.compile(
    r"主线|领涨|龙头|热点|题材|板块轮动|主线逻辑|核心主线|主攻方向|风口",
)

# 板块类关键词
SECTOR_KEYWORDS = re.compile(
    r"板块|行业|赛道|产业链|概念股|概念板块|题材板块",
)

# 情绪类关键词
SENTIMENT_KEYWORDS = re.compile(
    r"情绪|赚钱效应|恐慌|贪婪|乐观|悲观|市场信心|资金面|情绪面|情绪周期|冰点|高潮",
)

# 涨停类关键词
LIMIT_UP_KEYWORDS = re.compile(
    r"涨停|连板|炸板|封板|打板|龙头股|妖股|地天板|天地板",
)

# 关注类关键词
WATCHLIST_KEYWORDS = re.compile(
    r"关注|重点|留意|观察|跟踪|纳入视野|值得注意|值得跟踪",
)

# 风险类关键词
RISK_KEYWORDS = re.compile(
    r"风险|预警|警惕|注意|谨慎|回调|下跌|利空|减持|解禁|退市|暴雷|黑天鹅|灰犀牛",
)


def compute_relevance_score(title: str, summary: str, content_available: bool) -> int:
    """计算文章的市场相关度分数（确定性信号）。

    Args:
        title: 文章标题
        summary: 文章摘要
        content_available: 是否有正文内容

    Returns:
        相关度分数（0-100）
    """
    score = 0
    text = f"{title} {summary}"

    # 复盘类（最强信号）
    if REVIEW_KEYWORDS.search(text):
        score += 30

    # 策略类（强信号）
    if STRATEGY_KEYWORDS.search(text):
        score += 25

    # 主线类
    if MAINLINE_KEYWORDS.search(text):
        score += 15

    # 板块类
    if SECTOR_KEYWORDS.search(text):
        score += 10

    # 情绪类
    if SENTIMENT_KEYWORDS.search(text):
        score += 10

    # 涨停类
    if LIMIT_UP_KEYWORDS.search(text):
        score += 10

    # 关注/看盘类
    if WATCHLIST_KEYWORDS.search(text):
        score += 5

    # 风险类
    if RISK_KEYWORDS.search(text):
        score += 5

    # 有内容加成
    if content_available:
        score += 5

    return min(score, 100)


# ---------------------------------------------------------------------------
# AI 提取 Prompt
# ---------------------------------------------------------------------------

EVIDENCE_EXTRACTION_PROMPT = """你是一个A股市场文章分析专家。请分析以下公众号文章，提取结构化的市场观点证据。

要求：
1. 仅从文章内容中提取明确提到的信息，不得臆测或编造
2. 所有提取结果应标记为"作者观点"而非"市场事实"
3. 如果文章不是市场复盘/策略类内容，请标记为低相关度
4. 返回严格的 JSON 格式

文章标题：{title}
{content_section}

请返回以下 JSON 格式（不要包含其他文字）：
{{
    "article_type": "review|strategy|news|commentary|other",
    "relevance": "high|medium|low|unrelated",
    "time_role": "post_close_review|pre_market_strategy|intraday|unknown",
    "mentioned_sectors": ["板块名称1", "板块名称2"],
    "mentioned_stocks": ["股票名称(代码)"],
    "mainline_views": ["作者提出的主线观点1", "主线观点2"],
    "sentiment_view": "bullish|bearish|neutral|mixed",
    "next_day_watch_items": ["作者关注的明日方向1"],
    "risk_points": ["作者提到的风险点1"],
    "usable_summary": "50-100字的精炼摘要，保留关键观点"
}}"""


# ---------------------------------------------------------------------------
# ArticleEvidenceService
# ---------------------------------------------------------------------------


class ArticleEvidenceService:
    """文章证据服务 — 提取、缓存、查询公众号文章的市场观点证据。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 缓存查询
    # ------------------------------------------------------------------

    async def get_cached_evidence(
        self,
        article_id: int,
    ) -> MarketArticleEvidence | None:
        """获取缓存的文章证据。

        Args:
            article_id: 文章 ID

        Returns:
            缓存的证据对象，无缓存或缓存无效返回 None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ArticleProcessing)
                .where(ArticleProcessing.article_id == article_id)
                .where(ArticleProcessing.task_type == TASK_TYPE)
                .where(ArticleProcessing.status == "success")
                .order_by(ArticleProcessing.processed_at.desc())
            )
            processing = result.scalar_one_or_none()

        if not processing or not processing.result:
            return None

        return parse_evidence_json(processing.result)

    # ------------------------------------------------------------------
    # 单篇文章证据提取
    # ------------------------------------------------------------------

    async def extract_evidence(
        self,
        article_id: int,
        *,
        force: bool = False,
    ) -> ArticleEvidenceRecord:
        """提取单篇文章的市场观点证据。

        Args:
            article_id: 文章 ID
            force: 是否强制刷新（忽略缓存）

        Returns:
            带有提取结果的证据记录
        """
        # 加载文章和关联的 feed
        article, feed_name, feed_weight, provider = await self._load_article_with_feed(article_id)

        if not article:
            return ArticleEvidenceRecord(
                article_id=article_id,
                title="",
                evidence=MarketArticleEvidence(),
                outcome=EvidenceOutcome.FAILED,
            )

        # 检查缓存
        if not force:
            cached = await self.get_cached_evidence(article_id)
            if cached:
                return ArticleEvidenceRecord(
                    article_id=article_id,
                    title=article.title or "",
                    evidence=cached,
                    outcome=EvidenceOutcome.REUSED,
                    feed_name=feed_name,
                    feed_weight=feed_weight,
                    provider=provider,
                )

        # 检查内容是否足够
        title = article.title or ""
        summary = article.summary or ""
        content = article.content or ""

        if not title and not summary and not content:
            return ArticleEvidenceRecord(
                article_id=article_id,
                title="",
                evidence=MarketArticleEvidence(),
                outcome=EvidenceOutcome.SKIPPED,
                feed_name=feed_name,
                feed_weight=feed_weight,
                provider=provider,
            )

        # 仅有标题，无摘要无内容 → 降级到 fallback
        if title and not summary and not content:
            fallback_evidence = MarketArticleEvidence(
                article_type="unknown",
                relevance=ArticleRelevance.LOW.value,
                usable_summary=title,
            )
            return ArticleEvidenceRecord(
                article_id=article_id,
                title=title,
                evidence=fallback_evidence,
                outcome=EvidenceOutcome.FALLBACK,
                feed_name=feed_name,
                feed_weight=feed_weight,
                provider=provider,
            )

        # 调用 AI 提取
        try:
            evidence = await self._call_ai_extraction(title, summary, content)
        except Exception as e:
            logger.warning("文章证据 AI 提取失败 [article_id=%d]: %s", article_id, e)
            # 降级到 fallback
            fallback_evidence = MarketArticleEvidence(
                article_type="unknown",
                relevance=ArticleRelevance.LOW.value,
                usable_summary=summary[:200] if summary else title,
            )
            return ArticleEvidenceRecord(
                article_id=article_id,
                title=title,
                evidence=fallback_evidence,
                outcome=EvidenceOutcome.FAILED,
                feed_name=feed_name,
                feed_weight=feed_weight,
                provider=provider,
            )

        # 提取成功但无效 → fallback
        if evidence is None:
            fallback_evidence = MarketArticleEvidence(
                article_type="unknown",
                relevance=ArticleRelevance.LOW.value,
                usable_summary=summary[:200] if summary else title,
            )
            return ArticleEvidenceRecord(
                article_id=article_id,
                title=title,
                evidence=fallback_evidence,
                outcome=EvidenceOutcome.FALLBACK,
                feed_name=feed_name,
                feed_weight=feed_weight,
                provider=provider,
            )

        # 持久化成功提取的证据
        await self._persist_evidence(article_id, evidence)

        return ArticleEvidenceRecord(
            article_id=article_id,
            title=title,
            evidence=evidence,
            outcome=EvidenceOutcome.PREPARED,
            feed_name=feed_name,
            feed_weight=feed_weight,
            provider=provider,
        )

    # ------------------------------------------------------------------
    # 批量准备
    # ------------------------------------------------------------------

    async def prepare_batch(
        self,
        articles: list[dict[str, Any]],
        *,
        force: bool = False,
        max_candidates: int = MAX_CANDIDATES,
    ) -> BatchPreparationResult:
        """批量准备文章证据（有界候选集）。

        Args:
            articles: 文章字典列表（需包含 id, title, summary, content）
            force: 是否强制刷新
            max_candidates: 最大候选数

        Returns:
            批量准备结果
        """
        result = BatchPreparationResult(total=len(articles))

        # 按相关度排序并截取候选集
        scored = []
        for a in articles:
            score = compute_relevance_score(
                title=a.get("title", ""),
                summary=a.get("summary", ""),
                content_available=bool(a.get("content")),
            )
            scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        candidates = [a for _, a in scored[:max_candidates]]

        for article in candidates:
            article_id = article.get("id")
            if not article_id:
                continue

            record = await self.extract_evidence(article_id, force=force)
            result.records.append(record)

            # 计数
            if record.outcome == EvidenceOutcome.PREPARED:
                result.prepared += 1
            elif record.outcome == EvidenceOutcome.REUSED:
                result.reused += 1
            elif record.outcome == EvidenceOutcome.SKIPPED:
                result.skipped += 1
            elif record.outcome == EvidenceOutcome.FAILED:
                result.failed += 1
            elif record.outcome == EvidenceOutcome.INVALID:
                result.invalid += 1
            elif record.outcome == EvidenceOutcome.FALLBACK:
                result.fallback += 1

        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _load_article_with_feed(
        self,
        article_id: int,
    ) -> tuple[Article | None, str, int, str]:
        """加载文章及其关联的 feed 元数据。

        Returns:
            (article, feed_name, feed_weight, provider)
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            article = result.scalar_one_or_none()

            if not article:
                return None, "", 5, ""

            feed_name = ""
            feed_weight = 5
            provider = article.provider or ""

            if article.feed_id:
                feed_result = await session.execute(
                    select(Feed).where(Feed.id == article.feed_id)
                )
                feed = feed_result.scalar_one_or_none()
                if feed:
                    feed_name = feed.name or ""
                    feed_weight = feed.weight if feed.weight is not None else 5
                    if not provider:
                        provider = feed.provider or ""

        return article, feed_name, feed_weight, provider

    async def _call_ai_extraction(
        self,
        title: str,
        summary: str,
        content: str,
    ) -> MarketArticleEvidence | None:
        """调用 AI 提取文章证据。

        Args:
            title: 文章标题
            summary: 文章摘要
            content: 文章内容

        Returns:
            提取的证据对象，失败返回 None
        """
        from src.services.ai_processor import AIProcessor

        # 构建内容区段（优先 summary，其次 content 截断）
        if summary:
            content_section = f"文章摘要：{summary}"
        elif content:
            content_section = f"文章内容（节选）：{content[:3000]}"
        else:
            content_section = "（无可用内容）"

        prompt = EVIDENCE_EXTRACTION_PROMPT.format(
            title=title,
            content_section=content_section,
        )

        # 通过 AIProcessor 的底层 API 调用
        settings = __import__("config.settings", fromlist=["get_settings"]).get_settings()
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

        try:
            response = await client.messages.create(
                model=settings.llm_model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw_text += block.text

            # 提取 JSON
            json_match = re.search(r"\{[^{}]*\{.*?\}[^{}]*\}", raw_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)

            if json_match:
                return parse_evidence_json(json_match.group())

            return None

        except Exception as e:
            logger.warning("AI 文章证据提取调用失败: %s", e)
            return None

    async def _persist_evidence(
        self,
        article_id: int,
        evidence: MarketArticleEvidence,
    ) -> None:
        """持久化证据到 ArticleProcessing。

        Args:
            article_id: 文章 ID
            evidence: 提取的证据
        """
        try:
            async with self.db.get_session() as session:
                # 删除旧记录（如果存在）
                old_result = await session.execute(
                    select(ArticleProcessing)
                    .where(ArticleProcessing.article_id == article_id)
                    .where(ArticleProcessing.task_type == TASK_TYPE)
                )
                for old in old_result.scalars().all():
                    await session.delete(old)

                # 插入新记录
                processing = ArticleProcessing(
                    article_id=article_id,
                    task_type=TASK_TYPE,
                    status="success",
                    result=json.dumps(evidence.to_dict(), ensure_ascii=False),
                )
                session.add(processing)
                await session.commit()

        except Exception as e:
            logger.warning("文章证据持久化失败 [article_id=%d]: %s", article_id, e)
