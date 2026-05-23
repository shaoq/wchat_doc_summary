"""请求错误诊断格式化工具 - 为 httpx.RequestError 提供结构化的诊断信息。"""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

# 敏感查询参数名（不区分大小写）
_SENSITIVE_PARAMS = frozenset({
    "key", "token", "k", "api_key", "apikey", "secret", "auth",
    "access_token",
})


def _redact_url(url: str) -> str:
    """脱敏 URL 中的敏感查询参数值。"""
    parsed = urlparse(url)
    if not parsed.query:
        return url

    params = parse_qs(parsed.query, keep_blank_values=True)
    pairs: list[str] = []
    for key, values in params.items():
        for val in values:
            if key.lower() in _SENSITIVE_PARAMS:
                pairs.append(f"{key}=***")
            else:
                pairs.append(f"{key}={val}")

    new_query = "&".join(pairs)
    return urlunparse(parsed._replace(query=new_query))


def format_request_error(error: httpx.RequestError) -> str:
    """将 httpx.RequestError 格式化为包含诊断上下文的字符串。

    输出包含：
    - 异常类名（如 ConnectTimeout、ReadError）
    - 非空时的异常消息
    - 可用时的脱敏请求 URL
    - 可用时的底层原因类名和消息

    Args:
        error: httpx 请求异常

    Returns:
        格式化的诊断字符串
    """
    parts: list[str] = []

    # 异常类名
    exc_class = type(error).__name__
    parts.append(f"[{exc_class}]")

    # 非空消息
    msg = str(error).strip()
    if msg:
        parts.append(msg)

    # 脱敏的请求 URL
    try:
        if error.request and error.request.url:
            parts.append(f"url={_redact_url(str(error.request.url))}")
    except RuntimeError:
        pass

    # 底层原因
    cause = error.__cause__
    if cause is not None:
        cause_class = type(cause).__name__
        cause_msg = str(cause).strip()
        if cause_msg:
            parts.append(f"cause={cause_class}: {cause_msg}")
        else:
            parts.append(f"cause={cause_class}")

    return " | ".join(parts) if parts else exc_class
