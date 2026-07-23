"""StructPilot v6.0 — 术语规范化工具

将自然语言输入中的术语别名转换为标准形式。
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_ALIASES_PATH = BASE_DIR / "knowledge_base" / "terminology" / "parameter_aliases.json"


def load_terminology_map() -> dict[str, str]:
    """加载术语映射表（别名 -> 标准术语）"""
    try:
        data = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
        term_map = {}

        for entry in data:
            canonical = entry.get("canonical", "")
            aliases = entry.get("aliases", [])

            for alias in aliases:
                term_map[alias.lower()] = canonical

        return term_map
    except Exception:
        return {}


def normalize_text(text: str) -> str:
    """将文本中的术语别名替换为标准形式"""
    term_map = load_terminology_map()

    normalized = text
    for alias, canonical in term_map.items():
        # 不区分大小写替换
        import re
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        normalized = pattern.sub(canonical, normalized)

    return normalized


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """从文本中提取关键词（简单版：基于词频）"""
    import re

    # 分词（简单按空格和标点分割）
    words = re.findall(r'\b[\w一-龥]+\b', text.lower())

    # 过滤停用词
    stopwords = {
        "的", "是", "在", "和", "了", "与", "中", "有", "为", "等",
        "to", "the", "a", "an", "in", "of", "and", "or", "is", "it",
    }
    words = [w for w in words if w not in stopwords and len(w) > 1]

    # 统计词频
    from collections import Counter
    word_freq = Counter(words)

    # 返回频率最高的 N 个
    return [w for w, _ in word_freq.most_common(top_n)]


def auto_extract_tags(title: str, symptoms: str, solution: str) -> list[str]:
    """从经验内容中自动提取标签"""
    combined_text = f"{title} {symptoms} {solution}"

    # 1. 提取关键词
    keywords = extract_keywords(combined_text, top_n=15)

    # 2. 加载已知术语列表
    term_map = load_terminology_map()
    known_terms = set(term_map.values())

    # 3. 筛选出术语类关键词
    tags = []
    for kw in keywords:
        # 如果关键词是已知术语，或长度>=3的专业词
        if kw in known_terms or (len(kw) >= 3 and not kw.isdigit()):
            tags.append(kw)

    return tags[:5]  # 最多返回5个标签
