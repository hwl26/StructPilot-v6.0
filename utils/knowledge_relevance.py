"""Conservative relevance checks for knowledge-grounded answers."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Sequence, Tuple


UNKNOWN_KNOWLEDGE_REPLY = (
    "当前知识库没有找到与这个问题直接相关的可靠内容，所以我不知道，"
    "不能给出参数、SOP 或操作结论。\n\n"
    "请补充具体软件、处理步骤、报错原文或截图；如果仍无匹配，请查阅官方文档或咨询有经验的操作者。"
)


_DOMAIN_TERMS = {
    "ctf", "fsc", "mrc", "star", "eer", "motion", "drift", "defocus",
    "pixel", "box", "dose", "particle", "particles", "micrograph",
    "micrographs", "picking", "classification", "class3d", "refine",
    "refinement", "polish", "polishing", "mask", "topaz", "gctf",
    "ctffind", "gpu", "cpu", "memory", "2d", "3d", "ab-initio",
    "abinitio", "relion", "cryosparc",
    "导入", "运动校正", "漂移", "散焦", "欠焦", "像散", "颗粒挑选",
    "颗粒提取", "二维分类", "三维分类", "分类", "重构", "精修", "抛光",
    "后处理", "锐化", "掩膜", "分辨率", "像素", "剂量", "电压",
    "微图", "显微照片", "内存", "显存", "功率谱", "傅里叶", "取向",
    "对称性", "冰厚", "增益参考", "球差", "像素尺寸", "盒子尺寸",
}

_SOFTWARE_CONTEXT_TERMS = {"relion", "cryosparc"}
_GENERIC_ASCII_TERMS = {
    "what", "why", "how", "when", "where", "which", "the", "and", "for",
    "with", "from", "this", "that", "error", "failed", "failure", "help",
    "sop", "qc", "job", "data", "result", "results", "step", "steps",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def query_evidence_terms(query: str) -> set[str]:
    """Return concrete cryo-EM terms that must be present in supporting evidence."""
    normalized = _normalize(query)
    terms = {term for term in _DOMAIN_TERMS if term in normalized}
    for token in re.findall(r"[a-z][a-z0-9_.+-]{2,}", normalized):
        if token not in _GENERIC_ASCII_TERMS:
            terms.add(token)
    return terms


def direct_support_terms(query: str, evidence: str) -> set[str]:
    terms = query_evidence_terms(query)
    if not terms:
        return set()
    haystack = _normalize(evidence)
    matched = {term for term in terms if term in haystack}
    non_context = terms - _SOFTWARE_CONTEXT_TERMS
    if non_context and not (matched & non_context):
        return set()
    if not non_context and not matched:
        return set()
    return matched


def has_direct_knowledge_support(query: str, evidence: str) -> bool:
    return bool(direct_support_terms(query, evidence))


def filter_direct_results(
    query: str,
    results: Iterable[Tuple[str, str, float]],
    *,
    min_score: float = 0.2,
) -> List[Tuple[str, str, float]]:
    """Keep only results that explicitly contain a concrete term from the query."""
    accepted: List[Tuple[str, str, float]] = []
    for doc_id, text, score in results:
        if float(score) < min_score:
            continue
        if has_direct_knowledge_support(query, f"{doc_id}\n{text}"):
            accepted.append((doc_id, text, float(score)))
    return accepted


def is_workflow_control_query(query: str) -> bool:
    normalized = _normalize(query)
    controls: Sequence[str] = (
        "下一步", "当前步骤", "当前阶段", "现在流程", "流程进度", "开始流程",
        "继续流程", "完成当前", "跳过当前", "生成报告", "当前站点", "切换到",
        "进度", "报告", "哪一步",
    )
    return any(item in normalized for item in controls)


def is_image_evidence_query(query: str) -> bool:
    normalized = _normalize(query)
    references = ("这张图", "这个图", "截图", "图片", "图像", "class 图", "结果图")
    return any(item in normalized for item in references)
