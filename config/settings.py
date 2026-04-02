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
    article_list_provider: Literal["weread", "wechat2rss"] = Field(
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

    # 应用配置
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="日志级别",
    )
    data_dir: Path = Field(
        default=Path("./data"),
        description="数据存储目录",
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
