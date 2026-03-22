"""数据模型定义 - 使用 SQLAlchemy ORM 定义数据库表结构。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Date
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
