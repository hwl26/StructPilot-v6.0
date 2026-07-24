"""StructPilot v6.0 — 经验描述智能检测。

使用规则引擎检测对话中的经验分享意图。
"""

from __future__ import annotations

import re

# 经验分享的关键词模式
_EXPERIENCE_PATTERNS = [
    r"我们?(实验室|课题组|团队|lab)",
    r"我(遇到|碰到|发现|经历)过",
    r"解决(方法|办法|方案)(是|：)",
    r"(成功|有效|管用)的(做法|方法|经验)",
    r"(踩坑|教训|经验)",
    r"(推荐|建议)(用|使用|设置)",
    r"(这样|这么)做.{0,20}(解决|搞定|fix)",
    r"(参数|设置).{0,15}(调|改|优化)成",
    r"最后(我|我们).{0,20}(解决|成功)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _EXPERIENCE_PATTERNS]


def detect_experience_sharing(text: str) -> bool:
    """检测文本是否包含经验分享意图。

    Parameters
    ----------
    text
        用户输入的文本

    Returns
    -------
    bool
        True 表示可能是经验分享
    """
    if not text or len(text) < 10:
        return False

    # 检查关键词模式
    match_count = sum(1 for pattern in _COMPILED_PATTERNS if pattern.search(text))

    # 命中2个以上模式，判定为经验分享
    return match_count >= 2


def extract_experience_snippet(text: str, max_length: int = 200) -> str:
    """提取经验描述的摘要。

    Parameters
    ----------
    text
        原始文本
    max_length
        最大长度

    Returns
    -------
    str
        摘要文本
    """
    if len(text) <= max_length:
        return text

    # 查找第一个句号、问号或换行
    for delim in ["。", "？", "！", "\n"]:
        idx = text.find(delim, max_length // 2)
        if 0 < idx < max_length:
            return text[: idx + 1]

    return text[:max_length] + "..."
