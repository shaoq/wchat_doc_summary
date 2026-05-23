"""HTML 内容检测工具 — 判断字符串是否明显包含 HTML 正文标记。"""

from __future__ import annotations

import re

# 常见 HTML 块级标签（小写）
_BLOCK_TAG_RE = re.compile(
    r"<\s*(?:p|div|br|span|h[1-6]|ul|ol|li|table|img|a|blockquote|section|article|figure|pre|code)\b",
    re.IGNORECASE,
)

# HTML 转义后的标签起始标记
_ESCAPED_TAG_RE = re.compile(r"&lt;(?:p|div|br|span|h[1-6]|ul|ol|li|img|a)\b", re.IGNORECASE)


def looks_like_html_body(text: str | None) -> bool:
    """判断字符串是否明显包含 HTML 正文内容。

    使用保守策略：仅当文本包含明确的 HTML 块级标签或转义标签标记时返回 True。
    偶尔包含尖括号的纯文本摘要不会误判。

    Args:
        text: 待检测字符串

    Returns:
        True 表示文本明显包含 HTML 标记
    """
    if not text:
        return False

    stripped = text.strip()
    if not stripped:
        return False

    # 快速路径：以 < 开头且包含块级标签
    if stripped.startswith("<") and _BLOCK_TAG_RE.search(stripped):
        return True

    # 转义标签标记路径
    if _ESCAPED_TAG_RE.search(stripped):
        return True

    return False
