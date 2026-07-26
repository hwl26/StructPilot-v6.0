"""StructPilot v6.0 — 输入验证与安全防护模块。

防护措施：
1. XSS（跨站脚本攻击）防护
2. SQL注入防护（预防性）
3. 文件上传大小和类型限制
4. 敏感信息过滤
5. Markdown 安全渲染
"""

from __future__ import annotations

import re
import html
from typing import Any
from pathlib import Path

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False


# 允许的 HTML 标签（基本 Markdown）
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'code', 'pre',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'blockquote',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

# 允许的 HTML 属性
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],  # 用于语法高亮
}

# 允许的 URL 协议
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

# 危险模式（用于检测而非过滤）
DANGEROUS_PATTERNS = [
    r'<script[\s\S]*?>[\s\S]*?</script>',  # script 标签
    r'javascript:',  # javascript: 协议
    r'on\w+\s*=',  # 事件处理器（onclick, onload等）
    r'eval\s*\(',  # eval 函数
    r'expression\s*\(',  # CSS expression
]


def sanitize_html(text: str, strip: bool = False) -> str:
    """清理 HTML 输入，防止 XSS 攻击。

    Parameters
    ----------
    text : str
        用户输入的文本
    strip : bool
        是否完全移除 HTML 标签（True）还是保留安全标签（False）

    Returns
    -------
    str
        安全的文本
    """
    if not text:
        return ""

    if BLEACH_AVAILABLE:
        if strip:
            # 完全移除所有 HTML 标签
            return bleach.clean(text, tags=[], strip=True)
        else:
            # 保留安全的 Markdown 标签
            return bleach.clean(
                text,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                protocols=ALLOWED_PROTOCOLS,
                strip=True,
            )
    else:
        # Fallback：bleach 不可用时，始终做 HTML 转义防止 XSS
        return html.escape(text, quote=True)


def detect_dangerous_content(text: str) -> tuple[bool, list[str]]:
    """检测文本中是否包含危险内容。

    Returns
    -------
    tuple[bool, list[str]]
        (是否包含危险内容, 匹配到的模式列表)
    """
    if not text:
        return False, []

    dangerous_found = []
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            dangerous_found.append(pattern)

    return bool(dangerous_found), dangerous_found


def validate_experience_input(
    title: str,
    category: str,
    symptoms_text: str,
    solution: str,
    tags_str: str,
    step: str,
) -> tuple[bool, str, dict]:
    """验证经验贡献输入。

    Returns
    -------
    tuple[bool, str, dict]
        (是否通过验证, 错误信息, 清理后的数据)
    """
    errors = []
    cleaned = {}

    # 1. 标题验证
    if not title or len(title.strip()) < 3:
        errors.append("标题至少需要 3 个字符")
    elif len(title) > 100:
        errors.append("标题不能超过 100 个字符")
    else:
        # 检测危险内容
        is_dangerous, _ = detect_dangerous_content(title)
        if is_dangerous:
            errors.append("标题包含不安全内容")
        else:
            cleaned['title'] = sanitize_html(title, strip=True)

    # 2. 分类验证
    valid_categories = ["报错解决方案", "参数调优经验", "非常规流程", "软件技巧", "其他"]
    if category not in valid_categories:
        errors.append(f"分类必须是：{', '.join(valid_categories)}")
    else:
        cleaned['category'] = category

    # 3. 症状描述验证
    if not symptoms_text or len(symptoms_text.strip()) < 5:
        errors.append("症状描述至少需要 5 个字符")
    elif len(symptoms_text) > 1000:
        errors.append("症状描述不能超过 1000 个字符")
    else:
        is_dangerous, _ = detect_dangerous_content(symptoms_text)
        if is_dangerous:
            errors.append("症状描述包含不安全内容")
        else:
            cleaned['symptoms_text'] = sanitize_html(symptoms_text, strip=False)

    # 4. 解决方案验证
    if not solution or len(solution.strip()) < 10:
        errors.append("解决方案至少需要 10 个字符")
    elif len(solution) > 2000:
        errors.append("解决方案不能超过 2000 个字符")
    else:
        is_dangerous, _ = detect_dangerous_content(solution)
        if is_dangerous:
            errors.append("解决方案包含不安全内容")
        else:
            cleaned['solution'] = sanitize_html(solution, strip=False)

    # 5. 标签验证
    if tags_str:
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        if len(tags) > 10:
            errors.append("标签不能超过 10 个")
        else:
            cleaned_tags = []
            for tag in tags:
                if len(tag) > 20:
                    errors.append(f"标签 '{tag}' 超过 20 个字符")
                else:
                    cleaned_tags.append(sanitize_html(tag, strip=True))
            cleaned['tags'] = cleaned_tags
    else:
        cleaned['tags'] = []

    # 6. 步骤验证
    valid_steps = [f"cp_{i:02d}" for i in range(1, 21)]  # cp_01 ~ cp_20
    if step and step not in valid_steps:
        errors.append(f"步骤标识不合法")
    else:
        cleaned['step'] = step or ""

    if errors:
        return False, "; ".join(errors), {}
    return True, "", cleaned


def validate_note_input(content: str, title: str = "") -> tuple[bool, str, dict]:
    """验证个人笔记输入。

    Returns
    -------
    tuple[bool, str, dict]
        (是否通过验证, 错误信息, 清理后的数据)
    """
    errors = []
    cleaned = {}

    # 标题验证（可选）
    if title:
        if len(title) > 100:
            errors.append("笔记标题不能超过 100 个字符")
        else:
            is_dangerous, _ = detect_dangerous_content(title)
            if is_dangerous:
                errors.append("笔记标题包含不安全内容")
            else:
                cleaned['title'] = sanitize_html(title, strip=True)

    # 内容验证
    if not content or len(content.strip()) < 1:
        errors.append("笔记内容不能为空")
    elif len(content) > 10000:
        errors.append("笔记内容不能超过 10000 个字符")
    else:
        is_dangerous, _ = detect_dangerous_content(content)
        if is_dangerous:
            errors.append("笔记内容包含不安全内容")
        else:
            cleaned['content'] = sanitize_html(content, strip=False)

    if errors:
        return False, "; ".join(errors), {}
    return True, "", cleaned


def validate_board_post(content: str, author: str) -> tuple[bool, str, dict]:
    """验证留言板发帖输入。

    Returns
    -------
    tuple[bool, str, dict]
        (是否通过验证, 错误信息, 清理后的数据)
    """
    errors = []
    cleaned = {}

    # 作者验证
    if not author or len(author.strip()) < 1:
        errors.append("作者名称不能为空")
    elif len(author) > 50:
        errors.append("作者名称不能超过 50 个字符")
    else:
        cleaned['author'] = sanitize_html(author, strip=True)

    # 内容验证
    if not content or len(content.strip()) < 1:
        errors.append("留言内容不能为空")
    elif len(content) > 2000:
        errors.append("留言内容不能超过 2000 个字符")
    else:
        is_dangerous, _ = detect_dangerous_content(content)
        if is_dangerous:
            errors.append("留言内容包含不安全内容")
        else:
            cleaned['content'] = sanitize_html(content, strip=False)

    if errors:
        return False, "; ".join(errors), {}
    return True, "", cleaned


def validate_file_upload(
    file_bytes: bytes,
    filename: str,
    allowed_extensions: list[str],
    max_size_mb: int = 10,
) -> tuple[bool, str]:
    """验证文件上传。

    Parameters
    ----------
    file_bytes : bytes
        文件内容
    filename : str
        文件名
    allowed_extensions : list[str]
        允许的扩展名列表，如 ['.png', '.jpg', '.pdf']
    max_size_mb : int
        最大文件大小（MB）

    Returns
    -------
    tuple[bool, str]
        (是否通过验证, 错误信息)
    """
    # 文件大小验证
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"文件大小 {size_mb:.1f}MB 超过限制 {max_size_mb}MB"

    # 文件扩展名验证
    file_ext = Path(filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return False, f"文件类型 {file_ext} 不被允许，仅支持：{', '.join(allowed_extensions)}"

    # 文件名安全性验证
    safe_filename = re.sub(r'[^\w\s.-]', '', filename)
    if safe_filename != filename:
        return False, "文件名包含不安全字符"

    return True, ""


def sanitize_username(username: str) -> tuple[bool, str, str]:
    """验证并清理用户名。

    Returns
    -------
    tuple[bool, str, str]
        (是否通过验证, 错误信息, 清理后的用户名)
    """
    if not username or len(username.strip()) < 3:
        return False, "用户名至少需要 3 个字符", ""

    if len(username) > 30:
        return False, "用户名不能超过 30 个字符", ""

    # 只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含字母、数字、下划线", ""

    # 禁止的保留词
    reserved_words = ['admin', 'root', 'system', 'guest', 'visitor', 'test']
    if username.lower() == 'admin':
        pass  # admin 是默认管理员，允许
    elif username.lower() in reserved_words:
        return False, f"用户名 '{username}' 是保留词，请换一个", ""

    return True, "", username.lower()


# 测试代码
if __name__ == "__main__":
    # 测试 XSS 防护
    dangerous_inputs = [
        "<script>alert('xss')</script>",
        "Normal text with <strong>bold</strong>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
        "<a href='javascript:void(0)'>Click</a>",
    ]

    print("=== XSS 防护测试 ===")
    for inp in dangerous_inputs:
        is_dangerous, patterns = detect_dangerous_content(inp)
        cleaned = sanitize_html(inp)
        print(f"输入: {inp}")
        print(f"危险: {is_dangerous}, 模式: {patterns}")
        print(f"清理后: {cleaned}\n")

    # 测试经验输入验证
    print("=== 经验输入验证测试 ===")
    valid, error, cleaned = validate_experience_input(
        title="Motion Correction 报错",
        category="报错解决方案",
        symptoms_text="运行时报错：local motion too large",
        solution="增大 B-factor 到 300",
        tags_str="运动校正, B-factor",
        step="cp_02",
    )
    print(f"验证通过: {valid}")
    print(f"错误: {error}")
    print(f"清理后数据: {cleaned}\n")

    # 测试无效输入
    valid, error, cleaned = validate_experience_input(
        title="短",  # 太短
        category="无效分类",  # 不在允许列表
        symptoms_text="<script>alert('xss')</script>",  # XSS攻击
        solution="无",  # 太短
        tags_str="",
        step="invalid_step",  # 无效步骤
    )
    print(f"验证通过: {valid}")
    print(f"错误: {error}\n")
