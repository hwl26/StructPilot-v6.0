"""StructPilot v6.0 — 经验相似度匹配

根据用户问题或质检结果，查找相似的课题组经验。
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def load_all_experiences() -> list[dict]:
    """加载所有课题组经验"""
    try:
        data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        return data.get("entries", [])
    except Exception:
        return []


def calculate_similarity(query: str, experience: dict) -> float:
    """计算查询与经验的相似度（简单关键词匹配）"""
    from utils.terminology import extract_keywords

    # 提取查询关键词
    query_keywords = set(extract_keywords(query, top_n=20))

    # 提取经验关键词
    exp_text = (
        f"{experience.get('title', '')} "
        f"{experience.get('symptoms_text', '')} "
        f"{experience.get('solution', '')}"
    )
    exp_keywords = set(extract_keywords(exp_text, top_n=30))

    # 计算交集
    common = query_keywords & exp_keywords

    if not query_keywords:
        return 0.0

    # 相似度 = 交集大小 / 查询关键词数
    similarity = len(common) / len(query_keywords)

    # 如果标签也匹配，提升权重
    exp_tags = set(experience.get("tags", []))
    tag_boost = len(query_keywords & exp_tags) * 0.1

    return min(similarity + tag_boost, 1.0)


def find_similar_experiences(
    query: str,
    current_step: str = "",
    top_k: int = 3,
    min_similarity: float = 0.2,
) -> list[tuple[dict, float]]:
    """查找相似经验，返回 [(经验, 相似度), ...]"""
    all_experiences = load_all_experiences()

    # 1. 过滤当前步骤（如果指定）
    if current_step:
        step_experiences = [e for e in all_experiences if e.get("step") == current_step]
    else:
        step_experiences = all_experiences

    # 2. 计算相似度
    scored_experiences = []
    for exp in step_experiences:
        score = calculate_similarity(query, exp)
        if score >= min_similarity:
            scored_experiences.append((exp, score))

    # 3. 按相似度排序
    scored_experiences.sort(key=lambda x: x[1], reverse=True)

    # 4. 优先返回已验证的经验
    approved = [(e, s) for e, s in scored_experiences if e.get("status") == "approved"]
    pending = [(e, s) for e, s in scored_experiences if e.get("status") == "pending"]

    result = approved[:top_k]
    if len(result) < top_k:
        result.extend(pending[: top_k - len(result)])

    return result[:top_k]
