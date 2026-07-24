"""StructPilot v6.0 — 经验库去重检测。

使用 Levenshtein 距离检测标题相似度，避免重复提交。
"""

from __future__ import annotations


def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 距离（编辑距离）。"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # 插入、删除、替换的代价都是 1
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """计算两个字符串的相似度（0-1，1表示完全相同）。"""
    s1_clean = s1.strip().lower()
    s2_clean = s2.strip().lower()

    if not s1_clean or not s2_clean:
        return 0.0

    distance = levenshtein_distance(s1_clean, s2_clean)
    max_len = max(len(s1_clean), len(s2_clean))

    return 1.0 - (distance / max_len)


def find_similar_experiences(
    new_title: str,
    existing_experiences: list[dict],
    threshold: float = 0.80,
) -> list[dict]:
    """在已有经验库中查找与新标题相似的条目。

    Parameters
    ----------
    new_title
        新经验的标题
    existing_experiences
        已有经验列表，每条包含 {"title": ..., "id": ...}
    threshold
        相似度阈值（0-1），超过此值视为重复

    Returns
    -------
    list[dict]
        相似的经验列表，每条包含 {"entry": {...}, "similarity": float}
    """
    similar = []
    for exp in existing_experiences:
        title = exp.get("title", "")
        sim = similarity_ratio(new_title, title)
        if sim >= threshold:
            similar.append({"entry": exp, "similarity": sim})

    return sorted(similar, key=lambda x: x["similarity"], reverse=True)
