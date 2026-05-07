"""HTML 转 Markdown 转换器。

将微信公众号文章的 HTML 内容转换为格式良好的 Markdown 文本。
"""

import re

from markdownify import MarkdownConverter


# 残留 HTML 标签清理正则
_RE_RESIDUAL_HTML = re.compile(r"</?(?:section|span|div|article|font|center)[^>]*>", re.IGNORECASE)

# 连续空行压缩：3 个及以上换行 → 2 个换行（1 个空行）
_RE_MULTIPLE_BLANKS = re.compile(r"\n{3,}")

# 开头/结尾多余空行
_RE_TRIM_BLANKS = re.compile(r"^\n+|\n+$")


class WechatConverter(MarkdownConverter):
    """微信公众号 HTML 转换器。

    针对微信公众号文章的 HTML 特点做了定制：
    - 嵌套 <section> 标签不产生额外空行
    - <br> 标签转为换行
    """

    def convert_section(self, el, text, parent_tags=None):  # type: ignore[override]
        """section 标签仅返回内容，不添加额外格式。"""
        return text

    def convert_span(self, el, text, parent_tags=None):  # type: ignore[override]
        """span 标签仅返回内容。"""
        return text

    def convert_br(self, el, text, parent_tags=None):  # type: ignore[override]
        """br 标签转为换行。"""
        return "\n"

    def convert_font(self, el, text, parent_tags=None):  # type: ignore[override]
        """font 标签仅返回内容。"""
        return text

    def convert_center(self, el, text, parent_tags=None):  # type: ignore[override]
        """center 标签仅返回内容。"""
        return text


def html_to_markdown(html: str) -> str:
    """将 HTML 转换为 Markdown 格式。

    Args:
        html: 微信公众号文章的 HTML 内容

    Returns:
        格式良好的 Markdown 文本
    """
    if not html or not html.strip():
        return ""

    # 使用定制转换器
    md = WechatConverter(
        heading_style="atx",
        bullets="-",
        strong_em_symbol="*",
        code_language="",
        strip=["script", "style"],
    ).convert(html)

    # 清理残留 HTML 标签
    md = _RE_RESIDUAL_HTML.sub("", md)

    # 压缩连续空行
    md = _RE_MULTIPLE_BLANKS.sub("\n\n", md)

    # 去除首尾空行
    md = _RE_TRIM_BLANKS.sub("", md)

    return md
