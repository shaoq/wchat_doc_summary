"""数据模型定义 - 使用 SQLAlchemy ORM 定义数据库表结构。"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass


class Feed(Base):
    """公众号/订阅源模型。"""

    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mp_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True, comment="公众号ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="公众号名称")
    intro: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="简介")
    cover: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="封面图片URL")
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="列表Provider")
    provider_feed_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Provider侧订阅标识",
    )
    provider_meta: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Provider元数据(JSON)",
    )
    weight: Mapped[int] = mapped_column(
        Integer,
        default=5,
        comment="权重: 0-低, 5-中, 10-高",
    )
    status: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="状态: 0-停用, 1-启用",
    )
    sync_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="最后同步时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, name='{self.name}')>"


class FetchBatch(Base):
    """批量抓取进度跟踪模型 - 记录每个订阅每日的抓取状态。"""

    __tablename__ = "fetch_batches"
    __table_args__ = (
        UniqueConstraint("mp_id", "batch_date", name="uq_fetch_batches_mp_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mp_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="公众号ID")
    batch_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="批次日期")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", comment="状态: pending/done",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<FetchBatch(mp_id='{self.mp_id}', date={self.batch_date}, status='{self.status}')>"


class Article(Base):
    """文章模型。"""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="所属公众号ID")
    article_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True, comment="文章ID")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="文章标题")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="文章内容(HTML)")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="AI生成的摘要")
    pic_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="封面图片URL")
    original_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="原文链接")
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="文章来源Provider")
    provider_item_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Provider侧文章标识",
    )
    publish_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="发布时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:30]}...')>"


class RSSSource(Base):
    """RSS 源模型 - 管理付费 WeChat RSS SaaS 的 RSS 源配置。"""

    __tablename__ = "rss_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, comment="源名称")
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="aggregate", comment="源类型: aggregate/category",
    )
    feed_url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="RSS Feed URL")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="rss", comment="Provider 标识")
    provider_source_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Provider 侧源标识",
    )
    provider_metadata: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Provider 元数据(JSON)",
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, comment="状态: 0-停用, 1-启用",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<RSSSource(id={self.id}, name='{self.source_name}', type='{self.source_type}')>"


class RSSSourceHealth(Base):
    """RSS 源健康状态模型。"""

    __tablename__ = "rss_source_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rss_sources.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True, comment="RSS 源 ID",
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最近成功抓取时间",
    )
    latest_item_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Feed 中最新条目时间",
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, default=0, comment="连续失败次数",
    )
    empty_response_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="空响应累计次数",
    )
    last_error_summary: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="最近错误摘要",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<RSSSourceHealth(source_id={self.source_id}, failures={self.consecutive_failures})>"


class RSSArticleMembership(Base):
    """RSS 文章-源成员关系模型 - 文章可属于多个 RSS 源。"""

    __tablename__ = "rss_article_membership"
    __table_args__ = (
        UniqueConstraint("article_id", "source_id", name="uq_rss_article_membership"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="文章 ID",
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rss_sources.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="RSS 源 ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<RSSArticleMembership(article_id={self.article_id}, source_id={self.source_id})>"


class Auth(Base):
    """认证令牌模型。"""

    __tablename__ = "auths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="认证令牌")
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户名")
    status: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="状态: 0-失效, 1-有效",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<Auth(id={self.id}, username='{self.username}')>"


class ArticleProcessing(Base):
    """文章 AI 处理记录模型。"""

    __tablename__ = "article_processing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="文章ID",
    )
    task_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="任务类型: extract_stocks, summarize, etc.",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="状态: success, failed, skipped",
    )
    result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="处理结果(JSON格式)",
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="处理时间",
    )

    def __repr__(self) -> str:
        return f"<ArticleProcessing(id={self.id}, article_id={self.article_id}, task_type='{self.task_type}')>"


class MarketSummary(Base):
    """市场总结模型。"""

    __tablename__ = "market_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="交易日期",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="总结内容(Markdown)")
    data_sources: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="数据来源(JSON格式)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<MarketSummary(id={self.id}, trade_date='{self.trade_date}')>"


class CLSTelegraph(Base):
    """财联社电报模型。"""

    __tablename__ = "cls_telegraphs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegraph_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="电报ID",
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="标题")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="内容")
    ctime: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="发布时间戳")
    level: Mapped[str] = mapped_column(String(1), default="C", index=True, comment="重要程度 A/B/C")
    category: Mapped[str] = mapped_column(String(32), default="red", comment="分类")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="抓取时间",
    )

    def __repr__(self) -> str:
        return f"<CLSTelegraph(id={self.id}, title='{self.title[:30]}...')>"


class CLSWatchData(Base):
    """财联社看盘数据模型。"""

    __tablename__ = "cls_watch_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watch_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="数据唯一标识",
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="标题")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="内容")
    ctime: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="发布时间戳")
    category: Mapped[str] = mapped_column(String(32), default="watch", comment="分类")
    data_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="数据类型")
    stocks: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="关联股票(JSON)")
    sectors: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="关联板块(JSON)")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="抓取时间",
    )

    def __repr__(self) -> str:
        return f"<CLSWatchData(id={self.id}, title='{self.title[:30]}...')>"


# ===== 板块数据模型（用于 API 响应，不持久化到数据库）=====


@dataclass
class SectorData:
    """板块数据模型 - 用于存储从东方财富 API 获取的板块信息。"""

    code: str  # 板块代码（f12）
    name: str  # 板块名称（f14）
    price: Optional[float] = None  # 最新价（f2）
    change_pct: Optional[float] = None  # 涨跌幅（f3）
    change: Optional[float] = None  # 涨跌额（f4）
    volume: Optional[float] = None  # 成交量-手（f5）
    amount: Optional[float] = None  # 成交额（f6）
    high: Optional[float] = None  # 最高价（f15）
    low: Optional[float] = None  # 最低价（f16）
    open: Optional[float] = None  # 今开（f17）
    prev_close: Optional[float] = None  # 昨收（f18）
    main_inflow: Optional[float] = None  # 主力净流入（f62）
    super_large_inflow: Optional[float] = None  # 超大单净流入（f66）
    super_large_inflow_pct: Optional[float] = None  # 超大单净占比（f69）
    large_inflow: Optional[float] = None  # 大单净流入（f72）
    medium_inflow: Optional[float] = None  # 中单净流入（f78）
    small_inflow: Optional[float] = None  # 小单净流入（f84）

    def __repr__(self) -> str:
        return f"<SectorData(code={self.code}, name='{self.name}', change_pct={self.change_pct}%)>"


# ===== 市场数据缓存模型 =====


class MarketIndex(Base):
    """指数数据缓存模型。"""

    __tablename__ = "market_indices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="交易日期",
    )
    sh_index_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="上证指数名称")
    sh_index_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="上证指数价格")
    sh_index_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="上证指数涨跌幅")
    sz_index_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="深证成指名称")
    sz_index_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="深证成指价格")
    sz_index_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="深证成指涨跌幅")
    cy_index_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="创业板指名称")
    cy_index_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="创业板指价格")
    cy_index_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="创业板指涨跌幅")
    fetch_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="获取时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<MarketIndex(trade_date='{self.trade_date}')>"


class MarketVolume(Base):
    """成交额数据缓存模型。"""

    __tablename__ = "market_volume"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="交易日期",
    )
    sh_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="沪市成交额(亿)")
    sz_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="深市成交额(亿)")
    total_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="两市总成交额(亿)")
    fetch_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="获取时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<MarketVolume(trade_date='{self.trade_date}')>"


class MarketStatistics(Base):
    """涨跌统计数据缓存模型。"""

    __tablename__ = "market_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="交易日期",
    )
    up_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="上涨家数")
    down_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="下跌家数")
    flat_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="平盘家数")
    fetch_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="获取时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<MarketStatistics(trade_date='{self.trade_date}')>"


class MarketSector(Base):
    """板块数据缓存模型。"""

    __tablename__ = "market_sectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="交易日期",
    )
    sector_code: Mapped[str] = mapped_column(String(16), nullable=False, comment="板块代码")
    sector_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="板块名称")
    change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="涨跌幅")
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="成交额")
    main_inflow: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="主力净流入")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    __table_args__ = (
        UniqueConstraint("trade_date", "sector_code", name="uq_market_sectors_date_code"),
        {},
    )

    def __repr__(self) -> str:
        return f"<MarketSector(trade_date='{self.trade_date}', code='{self.sector_code}')>"


class LimitUpStock(Base):
    """涨停股数据缓存模型。"""

    __tablename__ = "limit_up_stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="交易日期",
    )
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False, comment="股票代码")
    stock_name: Mapped[str] = mapped_column(String(32), nullable=False, comment="股票名称")
    change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="涨跌幅")
    limit_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="连板数")
    industry: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="所属行业")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_limit_up_stocks_date_code"),
        {},
    )

    def __repr__(self) -> str:
        return f"<LimitUpStock(trade_date='{self.trade_date}', code='{self.stock_code}')>"


class GlobalMarketContext(Base):
    """海外市场上下文缓存模型。"""

    __tablename__ = "global_market_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_a_trade_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="目标A股交易日期",
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, comment="状态: ok/partial/error")
    captured_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="系统抓取时间")
    as_of: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="行情时间")
    session: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="美股交易阶段")
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="数据来源")
    payload: Mapped[str] = mapped_column(Text, nullable=False, comment="标准化上下文(JSON)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<GlobalMarketContext(target_a_trade_date='{self.target_a_trade_date}', status='{self.status}')>"


class TrackedSector(Base):
    """板块跟踪档案模型 - 记录候选/跟踪板块的长期状态。"""

    __tablename__ = "tracked_sectors"
    __table_args__ = (
        UniqueConstraint("sector_code", name="uq_tracked_sectors_code"),
        UniqueConstraint("canonical_name", name="uq_tracked_sectors_canonical_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="规范名称",
    )
    sector_code: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, unique=True, comment="板块代码（来自行情源）",
    )
    aliases: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="别名列表(JSON数组)",
    )
    source_codes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="所有已知源代码(JSON数组)",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="板块分类(行业/概念/地区等)",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate",
        comment="状态: candidate/tracked/inactive/ignored",
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="发现来源(market_cache/cls_watch/manual等)",
    )
    first_seen_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="首次发现日期",
    )
    last_seen_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="最近出现日期",
    )
    last_updated_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="最近趋势更新日期",
    )
    discovery_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="发现原因描述",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<TrackedSector(id={self.id}, name='{self.canonical_name}', status='{self.status}')>"


class SectorTrendSummary(Base):
    """板块趋势总结模型 - 每次板块更新的快照。"""

    __tablename__ = "sector_trend_summaries"
    __table_args__ = (
        UniqueConstraint("sector_id", "end_date", name="uq_sector_trend_summaries_sector_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_sectors.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="板块ID",
    )
    sector_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="板块名称(快照)",
    )
    sector_code: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="板块代码(快照)",
    )
    end_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="快照结束日期",
    )
    window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="回看窗口天数",
    )
    trend_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="趋势状态标签",
    )
    strength_level: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="强度等级(强/中/弱)",
    )
    action_bias: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="操作倾向(跟踪/观察/回避)",
    )
    judgement: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="趋势研判摘要",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="完整报告内容(Markdown)",
    )
    evidence_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据数据(JSON)",
    )
    output_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="报告文件路径",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SectorTrendSummary(sector_name='{self.sector_name}', end_date='{self.end_date}')>"


class SectorGroup(Base):
    """板块分组模型 - 主题/产业链分组。"""

    __tablename__ = "sector_groups"
    __table_args__ = (
        UniqueConstraint("canonical_name", name="uq_sector_groups_canonical_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="规范名称",
    )
    aliases: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="别名列表(JSON数组)",
    )
    keywords: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="关键词列表(JSON数组)",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="分组描述",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active",
        comment="状态: active/inactive",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SectorGroup(id={self.id}, name='{self.canonical_name}', status='{self.status}')>"


class SectorGroupMember(Base):
    """分组成员映射模型 - 板块与分组的多对多关系。"""

    __tablename__ = "sector_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "sector_id", name="uq_sector_group_members_group_sector"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sector_groups.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="分组ID",
    )
    sector_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_sectors.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="板块ID",
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="related",
        comment="关系类型: core/upstream/downstream/material/equipment/catalyst/related",
    )
    weight: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=1.0, comment="权重",
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="来源(manual/suggestion/auto)",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="置信度(0-1)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SectorGroupMember(group_id={self.group_id}, sector_id={self.sector_id}, type='{self.relation_type}')>"


class SectorGroupSuggestion(Base):
    """分组建议模型 - 待确认的分组变更建议。"""

    __tablename__ = "sector_group_suggestions"
    __table_args__ = (
        Index(
            "uq_sector_group_suggestions_pending",
            "suggestion_type",
            "target_group_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="建议类型: new_group/add_members/update_members",
    )
    target_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sector_groups.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="目标分组ID(add_members/update_members时)",
    )
    suggested_group_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="建议的分组名称(new_group时)",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        comment="状态: pending/accepted/ignored/expired",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="置信度(0-1)",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="建议原因",
    )
    evidence_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据数据(JSON)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SectorGroupSuggestion(id={self.id}, type='{self.suggestion_type}', status='{self.status}')>"


class SectorGroupSuggestionMember(Base):
    """分组建议成员模型 - 建议中的具体成员变更。"""

    __tablename__ = "sector_group_suggestion_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sector_group_suggestions.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="建议ID",
    )
    sector_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracked_sectors.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="板块ID",
    )
    suggested_relation_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="建议的关系类型",
    )
    current_relation_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="当前关系类型(update_members时)",
    )
    suggested_weight: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="建议的权重",
    )
    current_weight: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="当前权重(update_members时)",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="置信度(0-1)",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="建议原因",
    )

    def __repr__(self) -> str:
        return f"<SectorGroupSuggestionMember(suggestion_id={self.suggestion_id}, sector_id={self.sector_id})>"


class SectorGroupTrendSummary(Base):
    """分组趋势总结模型 - 组级趋势跟踪报告。"""

    __tablename__ = "sector_group_trend_summaries"
    __table_args__ = (
        UniqueConstraint("group_id", "end_date", name="uq_sector_group_trend_summaries_group_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sector_groups.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="分组ID",
    )
    group_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="分组名称(快照)",
    )
    end_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="快照结束日期",
    )
    window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="回看窗口天数",
    )
    trend_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="组级趋势状态标签",
    )
    strength_level: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="强度等级(强/中/弱)",
    )
    action_bias: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="操作倾向(跟踪/观察/回避)",
    )
    judgement: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="研判摘要",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="完整报告内容(Markdown)",
    )
    evidence_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据数据(JSON)",
    )
    member_freshness_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="成员新鲜度数据(JSON)",
    )
    output_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="报告文件路径",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<SectorGroupTrendSummary(group_name='{self.group_name}', end_date='{self.end_date}')>"


class ThemeTermSuggestion(Base):
    """主题词建议模型 - 主题词典学习建议。"""

    __tablename__ = "theme_term_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="建议类型: add_to_existing_theme/create_theme/mark_noise/disable_term",
    )
    target_theme_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="目标主题名",
    )
    suggested_theme_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="建议新建的主题名",
    )
    term: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="候选主题词",
    )
    normalized_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="规范化键(comparison_key)",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        comment="状态: pending/accepted/ignored/expired",
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="置信度 0-1",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="AI/规则判断理由",
    )
    evidence_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="证据数据(JSON)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ThemeTermSuggestion(term='{self.term}', type='{self.suggestion_type}', status='{self.status}')>"


class AcceptedThemeTerm(Base):
    """已接受主题词记录 - 经用户确认的主题词学习结果。"""

    __tablename__ = "accepted_theme_terms"
    __table_args__ = (
        UniqueConstraint("theme_name", "normalized_key", name="uq_accepted_theme_terms_theme_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="主题名",
    )
    term: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="主题词",
    )
    normalized_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="规范化键",
    )
    source_suggestion_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="来源建议ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<AcceptedThemeTerm(theme='{self.theme_name}', term='{self.term}')>"
