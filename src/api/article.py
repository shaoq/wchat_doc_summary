"""文章内容抓取模块 - 从微信公众号抓取和解析文章内容。"""

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import get_settings
from src.api.request_error import format_request_error

logger = logging.getLogger(__name__)


class ArticleFetchError(Exception):
    """文章抓取错误。"""

    pass


async def fetch_article_content(article_ref: str) -> str:
    """请求微信公众号文章获取 HTML 内容。

    Args:
        article_ref: 文章 URL 或文章 ID（URL 中 /s/ 后面的部分）

    Returns:
        文章 HTML 内容

    Raises:
        ArticleFetchError: 抓取失败
    """
    settings = get_settings()
    if article_ref.startswith(("http://", "https://")):
        url = article_ref
    else:
        url = f"https://mp.weixin.qq.com/s/{article_ref}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(settings.max_retries + 1):
            try:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=settings.request_timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response.text
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 错误: {e.response.status_code}")
                if attempt == settings.max_retries:
                    raise ArticleFetchError(
                        f"获取文章失败: HTTP {e.response.status_code}"
                    ) from e
            except httpx.RequestError as e:
                logger.warning(f"请求错误 (尝试 {attempt + 1}): {format_request_error(e)}")
                if attempt == settings.max_retries:
                    raise ArticleFetchError(f"网络请求失败: {format_request_error(e)}") from e

    raise ArticleFetchError("未知错误")


def parse_article_html(html: str) -> dict[str, Any]:
    """解析微信公众号文章 HTML。

    Args:
        html: 文章 HTML 内容

    Returns:
        解析后的文章数据字典：
        - title: 标题
        - content: 正文 HTML（清洗后）
        - publish_time: 发布时间
        - author: 作者
        - cover: 封面图片 URL
    """
    soup = BeautifulSoup(html, "html.parser")

    result: dict[str, Any] = {
        "title": None,
        "content": None,
        "publish_time": None,
        "author": None,
        "cover": None,
    }

    # 提取标题
    title_elem = soup.find("h1", class_="rich_media_title") or soup.find(
        "meta", property="og:title"
    )
    if title_elem:
        if title_elem.name == "meta":
            result["title"] = title_elem.get("content", "").strip()
        else:
            result["title"] = title_elem.get_text(strip=True)

    # 提取作者
    author_elem = soup.find("a", id="js_name") or soup.find(
        "meta", property="article:author"
    )
    if author_elem:
        if author_elem.name == "meta":
            result["author"] = author_elem.get("content", "").strip()
        else:
            result["author"] = author_elem.get_text(strip=True)

    # 提取发布时间
    time_elem = soup.find("em", id="publish_time") or soup.find(
        "meta", property="article:published_time"
    )
    if time_elem:
        if time_elem.name == "meta":
            time_str = time_elem.get("content", "").strip()
        else:
            time_str = time_elem.get_text(strip=True)

        if time_str:
            result["publish_time"] = _parse_publish_time(time_str)

    # 提取封面图片
    cover_elem = soup.find("meta", property="og:image")
    if cover_elem:
        result["cover"] = cover_elem.get("content", "").strip()

    # 提取正文内容
    content_elem = soup.find("div", id="js_content")
    if content_elem:
        # 清洗内容
        result["content"] = _clean_content(str(content_elem))

    return result


def _parse_publish_time(time_str: str) -> datetime | None:
    """解析发布时间字符串。

    微信公众号的时间格式可能有多种：
    - "2024年1月1日"
    - "2024-01-01"
    - "2024-01-01 12:00"
    - ISO 8601 格式

    Args:
        time_str: 时间字符串

    Returns:
        解析后的 datetime 对象，解析失败返回 None
    """
    # 尝试多种格式
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    # 尝试使用正则提取日期
    match = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", time_str)
    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            pass

    logger.warning(f"无法解析时间: {time_str}")
    return None


def _clean_content(html: str) -> str:
    """清洗文章内容 HTML。

    - 移除脚本和样式标签
    - 移除 data-src 属性中的图片延迟加载，转为 src
    - 移除不必要的属性

    Args:
        html: 原始 HTML

    Returns:
        清洗后的 HTML
    """
    soup = BeautifulSoup(html, "html.parser")

    # 移除脚本和样式
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # 处理图片：将 data-src 转为 src
    for img in soup.find_all("img"):
        data_src = img.get("data-src")
        if data_src:
            img["src"] = data_src
            del img["data-src"]

    # 移除不需要的属性
    for tag in soup.find_all(True):
        attrs_to_remove = []
        for attr in tag.attrs:
            # 保留 class, style, src, href, alt 等基本属性
            if attr.startswith("data-") or attr in ["id", "onclick"]:
                attrs_to_remove.append(attr)
        for attr in attrs_to_remove:
            del tag[attr]

    return str(soup)


def extract_images(html: str) -> list[str]:
    """提取文章中的图片 URL 列表。

    Args:
        html: 文章 HTML 内容

    Returns:
        图片 URL 列表
    """
    soup = BeautifulSoup(html, "html.parser")
    images: list[str] = []

    for img in soup.find_all("img"):
        # 优先使用 src，其次 data-src（延迟加载）
        src = img.get("src") or img.get("data-src")
        if src and _is_valid_url(src):
            images.append(src)

    return images


def _is_valid_url(url: str) -> bool:
    """检查 URL 是否有效。

    Args:
        url: URL 字符串

    Returns:
        是否为有效的 URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False
