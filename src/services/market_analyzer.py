"""市场分析服务 - 生成 A 股市场总结。"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import chinese_calendar as calendar

from src.api.finance import FinanceClient, FinanceAPIError
from src.models.schema import Article, MarketSummary
from src.storage.database import Database, CRUDOperations

logger = logging.getLogger(__name__)

# 默认模板路径
DEFAULT_TEMPLATE_PATH = Path("templates/market_summary.md")
OUTPUT_DIR = Path("output/market_summaries")


class MarketAnalyzer:
    """市场分析服务。

    提供交易日判断、数据收集、总结生成等功能。
    """

    def __init__(self, db: Database, finance_client: FinanceClient | None = None) -> None:
        """初始化市场分析服务。

        Args:
            db: 数据库实例
            finance_client: 财经数据客户端（可选，默认创建新实例）
        """
        self.db = db
        self.finance_client = finance_client or FinanceClient()
        self._summary_crud = CRUDOperations(MarketSummary)
        self._article_crud = CRUDOperations(Article)

    def get_latest_trade_date(self, target_date: date | None = None) -> date:
        """获取最近的交易日。

        如果 target_date 是交易日，返回 target_date。
        如果 target_date 是非交易日（周末/节假日），返回最近一个已过去的交易日。

        Args:
            target_date: 目标日期，默认为今天

        Returns:
            最近的交易日
        """
        if target_date is None:
            target_date = date.today()

        # 从目标日期往前找交易日
        check_date = target_date
        max_days_back = 30  # 最多往前找 30 天

        for _ in range(max_days_back):
            if calendar.is_workday(check_date):
                return check_date
            check_date -= timedelta(days=1)

        # 如果 30 天内找不到，返回 target_date（降级处理）
        logger.warning(f"30 天内未找到交易日，使用 {target_date}")
        return target_date

    def is_trade_day(self, check_date: date | None = None) -> bool:
        """判断是否为交易日。

        Args:
            check_date: 待判断日期，默认为今天

        Returns:
            是否为交易日
        """
        if check_date is None:
            check_date = date.today()
        return calendar.is_workday(check_date)

    async def collect_market_data(self, offline: bool = False) -> dict[str, Any]:
        """收集市场数据。

        Args:
            offline: 是否仅使用本地数据（不联网获取行情）

        Returns:
            市场数据字典
        """
        if offline:
            logger.info("离线模式：跳过网络数据获取")
            return {
                "indices": {},
                "volume": {},
                "statistics": {},
                "sectors": {},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
                "offline": True,
            }

        try:
            return await self.finance_client.get_all_market_data()
        except FinanceAPIError as e:
            logger.error(f"获取市场数据失败: {e}")
            return {
                "indices": {},
                "volume": {},
                "statistics": {},
                "sectors": {},
                "limit_up": [],
                "fetch_time": datetime.now().isoformat(),
                "error": str(e),
            }

    async def get_related_articles(
        self,
        trade_date: date,
        days_back: int = 3,
    ) -> list[dict[str, Any]]:
        """获取与交易日相关的文章。

        Args:
            trade_date: 交易日期
            days_back: 往前查找天数

        Returns:
            文章列表（包含标题、摘要、内容）
        """
        start_date = trade_date - timedelta(days=days_back)

        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Article)
                .where(Article.publish_time >= start_date)
                .where(Article.publish_time <= trade_date + timedelta(days=1))
                .order_by(Article.publish_time.desc())
                .limit(50)
            )
            articles = result.scalars().all()

        return [
            {
                "title": a.title,
                "summary": a.summary or "",
                "content": (a.content or "")[:1000] if a.content else "",  # 限制长度
                "publish_time": a.publish_time.isoformat() if a.publish_time else None,
            }
            for a in articles
        ]

    async def generate_summary(
        self,
        trade_date: date,
        market_data: dict[str, Any],
        articles: list[dict[str, Any]],
        template_content: str | None = None,
    ) -> str:
        """生成市场总结（不使用 AI，仅格式化数据）。

        注意：实际的 AI 生成逻辑在 AIProcessor.generate_market_summary() 中。

        Args:
            trade_date: 交易日期
            market_data: 市场数据
            articles: 相关文章
            template_content: 模板内容（可选）

        Returns:
            格式化的市场总结
        """
        # 加载模板
        if template_content is None:
            template_content = self._load_template()

        # 格式化数据
        indices_summary = self._format_indices(market_data.get("indices", {}))
        volume = market_data.get("volume", {}).get("total_volume", "N/A")
        statistics = market_data.get("statistics", {})
        sectors = market_data.get("sectors", {})
        limit_up = market_data.get("limit_up", [])

        # 填充模板
        content = template_content.format(
            indices_summary=indices_summary,
            volume=volume,
            up_count=statistics.get("up_count", "N/A"),
            down_count=statistics.get("down_count", "N/A"),
            flat_count=statistics.get("flat_count", "N/A"),
            top_sectors=self._format_sectors(sectors.get("top_sectors", [])),
            bottom_sectors=self._format_sectors(sectors.get("bottom_sectors", [])),
            limit_up_stocks=self._format_stocks(limit_up),
            leading_stocks=self._format_stocks(limit_up[:5]),  # 龙头取前 5
            market_news=self._format_articles(articles[:10]),  # 取前 10 篇文章
        )

        return content

    async def save_summary(
        self,
        trade_date: date,
        content: str,
        data_sources: dict[str, Any],
    ) -> MarketSummary:
        """保存市场总结。

        同时保存到数据库和文件。

        Args:
            trade_date: 交易日期
            content: 总结内容
            data_sources: 数据来源信息

        Returns:
            保存的 MarketSummary 对象
        """
        # 保存到数据库
        async with self.db.get_session() as session:
            summary = MarketSummary(
                trade_date=trade_date,
                content=content,
                data_sources=json.dumps(data_sources, ensure_ascii=False),
            )
            session.add(summary)
            await session.flush()
            await session.refresh(summary)

        # 保存到文件
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        file_path = OUTPUT_DIR / f"{trade_date}.md"
        file_path.write_text(content, encoding="utf-8")

        logger.info(f"市场总结已保存: {file_path}")
        return summary

    async def get_existing_summary(self, trade_date: date) -> MarketSummary | None:
        """获取已存在的市场总结。

        Args:
            trade_date: 交易日期

        Returns:
            已存在的总结，不存在返回 None
        """
        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(MarketSummary).where(MarketSummary.trade_date == trade_date)
            )
            return result.scalar_one_or_none()

    async def list_summaries(
        self,
        limit: int = 10,
    ) -> list[MarketSummary]:
        """获取历史市场总结列表。

        Args:
            limit: 返回数量

        Returns:
            总结列表
        """
        async with self.db.get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(MarketSummary)
                .order_by(MarketSummary.trade_date.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    def _load_template(self) -> str:
        """加载模板文件。"""
        if DEFAULT_TEMPLATE_PATH.exists():
            return DEFAULT_TEMPLATE_PATH.read_text(encoding="utf-8")

        # 返回默认模板
        return """# 市场概览

## 指数表现
{indices_summary}

## 成交情况
两市成交额：{volume} 亿元

## 涨跌统计
- 上涨：{up_count} 家
- 下跌：{down_count} 家
- 平盘：{flat_count} 家

## 板块表现
### 涨幅榜
{top_sectors}

### 跌幅榜
{bottom_sectors}

## 连板个股
{limit_up_stocks}

## 龙头个股
{leading_stocks}

---

# 市场消息

{market_news}
"""

    def _format_indices(self, indices: dict[str, Any]) -> str:
        """格式化指数数据。"""
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

    def _format_sectors(self, sectors: list[dict[str, Any]]) -> str:
        """格式化板块数据。"""
        if not sectors:
            return "无数据"

        lines = []
        for s in sectors:
            name = s.get("name", "")
            change = s.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}: {sign}{change*100:.2f}%")

        return "\n".join(lines)

    def _format_stocks(self, stocks: list[dict[str, Any]]) -> str:
        """格式化个股数据。"""
        if not stocks:
            return "无数据"

        lines = []
        for s in stocks:
            name = s.get("name", "")
            code = s.get("code", "")
            change = s.get("change", 0)
            sign = "+" if change >= 0 else ""
            lines.append(f"- {name}({code}): {sign}{change*100:.2f}%")

        return "\n".join(lines)

    def _format_articles(self, articles: list[dict[str, Any]]) -> str:
        """格式化文章数据。"""
        if not articles:
            return "无相关文章"

        lines = []
        for a in articles:
            title = a.get("title", "")
            summary = a.get("summary", "")[:100] if a.get("summary") else ""
            lines.append(f"- **{title}**")
            if summary:
                lines.append(f"  {summary}...")

        return "\n".join(lines)
