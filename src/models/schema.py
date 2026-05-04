"""数据模型定义 - 使用 SQLAlchemy ORM 定义数据库表结构。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, Date
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
