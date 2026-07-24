"""StructPilot v6.0 — 输入验证和安全防护。

防止 XSS、路径遍历、SQL 注入等常见安全问题。
"""

from __future__ import annotations

import html
import re
from pathlib import Path


def sanitize_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 攻击。

    Parameters
    ----------
    text
        用户输入的文本

    Returns
    -------
    str
        转义后的安全文本
    """
    if not text:
        return ""
    return html.escape(text, quote=True)


def validate_file_path(path: str, allowed_base: Path) -> Path | None:
    """验证文件路径，防止目录遍历攻击。

    Parameters
    ----------
    path
        用户提供的文件路径
    allowed_base
        允许访问的基础目录

    Returns
    -------
    Path | None
        验证通过返回 Path，否则返回 None
    """
    try:
        resolved = Path(path).resolve()
        base_resolved = allowed_base.resolve()

        # 检查是否在允许的目录内
        if not str(resolved).startswith(str(base_resolved)):
            return None

        return resolved
    except Exception:
        return None


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符。

    Parameters
    ----------
    filename
        原始文件名

    Returns
    -------
    str
        安全的文件名
    """
    # 只保留字母、数字、下划线、连字符和点
    safe_name = re.sub(r'[^\w\-\.]', '_', filename)

    # 防止隐藏文件（以点开头）
    if safe_name.startswith('.'):
        safe_name = '_' + safe_name[1:]

    # 限制长度
    if len(safe_name) > 255:
        name_parts = safe_name.rsplit('.', 1)
        if len(name_parts) == 2:
            safe_name = name_parts[0][:250] + '.' + name_parts[1]
        else:
            safe_name = safe_name[:255]

    return safe_name or "unnamed"


def validate_json_size(data: str, max_size_mb: int = 10) -> bool:
    """验证 JSON 数据大小，防止内存耗尽。

    Parameters
    ----------
    data
        JSON 字符串
    max_size_mb
        最大允许大小（MB）

    Returns
    -------
    bool
        是否在允许范围内
    """
    size_bytes = len(data.encode('utf-8'))
    max_bytes = max_size_mb * 1024 * 1024
    return size_bytes <= max_bytes


def sanitize_user_input(text: str, max_length: int = 10000) -> str:
    """清理用户输入，移除危险内容。

    Parameters
    ----------
    text
        用户输入
    max_length
        最大允许长度

    Returns
    -------
    str
        清理后的文本
    """
    if not text:
        return ""

    # 限制长度
    text = text[:max_length]

    # 移除控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)

    # 转义 HTML
    text = html.escape(text, quote=False)

    return text
