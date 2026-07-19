"""配置管理模块 - 使用 pydantic-settings 实现类型安全的配置管理。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类。

    使用 pydantic-settings 从环境变量和 .env 文件加载配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 微信读书代理 API 配置
    weread_api_base: str = Field(
        default="https://weread.111965.xyz",
        description="微信读书 API 基础 URL",
    )
    article_list_provider: Literal["weread", "wechat2rss", "rss"] = Field(
        default="weread",
        description="文章列表 Provider",
    )
    wechat2rss_base_url: str = Field(
        default="https://wechat2rss.xlab.app",
        description="Wechat2RSS API 基础 URL",
    )
    wechat2rss_token: str | None = Field(
        default=None,
        description="Wechat2RSS API token",
    )

    # RSS Provider 配置
    wechat_rss_api_key: str | None = Field(
        default=None,
        description="微信 RSS SaaS 全局 API Key",
    )
    rss_content_mode: Literal["feed_only", "prefer_feed", "fetch_missing"] = Field(
        default="prefer_feed",
        description="RSS 内容模式: feed_only/prefer_feed/fetch_missing",
    )
    rss_stale_threshold_hours: int = Field(
        default=48,
        ge=1,
        description="RSS 源过期阈值（小时）",
    )
    wechat_rss_plan_limit: int | None = Field(
        default=None,
        description="微信 RSS SaaS 付费计划源数量上限（仅告警）",
    )
    rss_auto_subscribe_discovered_feeds: bool = Field(
        default=False,
        description="是否自动订阅 RSS 中发现的未知公众号",
    )
    rss_discovered_feed_default_status: Literal["active", "inactive"] = Field(
        default="inactive",
        description="自动发现的公众号默认状态: active/inactive",
    )
    rss_unknown_feed_policy: Literal["skip", "create_placeholder"] = Field(
        default="skip",
        description="未知公众号处理策略: skip(跳过文章)/create_placeholder(创建占位订阅)",
    )
    rss_identity_resolver_provider: Literal["weread", "wechat2rss"] = Field(
        default="weread",
        description="RSS 归属解析使用的身份提供者（用于从文章 URL 解析公众号身份，不能是 rss）",
    )

    # 数据库配置
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/wchat.db",
        description="SQLite 数据库连接字符串",
    )

    # LLM 配置 (支持任意兼容 Anthropic 协议的平台)
    llm_base_url: str = Field(
        default="https://api.anthropic.com",
        description="LLM API Base URL",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="LLM API Key",
    )
    llm_model: str = Field(
        default="claude-3-5-haiku-latest",
        description="模型名称",
    )

    # 网络请求配置
    request_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="请求超时时间（秒）",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="最大重试次数",
    )

    # 抓取配置
    fetch_page_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="每次 API 请求获取的文章数量",
    )
    fetch_page_interval: float = Field(
        default=6.0,
        ge=0,
        le=60,
        description="列表翻页间隔（秒）",
    )
    fetch_page_jitter: float = Field(
        default=3.0,
        ge=0,
        le=30,
        description="翻页间随机抖动上限（秒）",
    )
    fetch_article_interval: float = Field(
        default=6.0,
        ge=0,
        le=60,
        description="文章内容抓取间隔（秒）",
    )
    fetch_article_jitter: float = Field(
        default=3.0,
        ge=0,
        le=30,
        description="文章间随机抖动上限（秒）",
    )
    fetch_subscription_delay: float = Field(
        default=8.0,
        ge=0,
        le=120,
        description="订阅间基础等待（秒）",
    )
    fetch_subscription_jitter: float = Field(
        default=4.0,
        ge=0,
        le=30,
        description="订阅间抖动上限（秒）",
    )
    fetch_rate_limit: int = Field(
        default=12,
        ge=1,
        le=120,
        description="全局每分钟最大请求数",
    )
    fetch_rate_window: int = Field(
        default=60,
        ge=10,
        le=300,
        description="滑动窗口大小（秒）",
    )

    # 应用配置
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="日志级别",
    )
    data_dir: Path = Field(
        default=Path("./data"),
        description="数据存储目录",
    )

    # 市场数据源配置（TickFlow 切换）
    market_data_provider: Literal["off", "mixed", "tickflow"] = Field(
        default="tickflow",
        description="市场数据源: tickflow(默认,纯TickFlow+market-summary自动sync) / mixed(TickFlow主+原源fallback) / off(纯原源)",
    )
    tickflow_api_key: str | None = Field(
        default=None,
        description="TickFlow API Key（free 档可留空，走 free-api 服务器）",
    )
    tickflow_base_url: str | None = Field(
        default=None,
        description="TickFlow 自定义端点（留空用默认 free-api）",
    )

    def get_db_path(self) -> Path:
        """获取数据库文件路径。"""
        # 从 database_url 中提取路径
        db_path = self.database_url.split("///")[-1]
        return Path(db_path)

    def ensure_data_dir(self) -> None:
        """确保数据目录存在。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。

    使用 lru_cache 确保配置只加载一次。

    Returns:
        Settings: 配置实例
    """
    settings = Settings()
    settings.ensure_data_dir()
    return settings


# 导出全局配置实例
settings = get_settings()
