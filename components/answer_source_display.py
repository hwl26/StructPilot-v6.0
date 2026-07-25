"""StructPilot v6.0 — AI 回答来源分层展示组件（P0-2 + 延伸）

将 trace["citations"] 按来源类型拆分为三层渲染：
  📚 基础原理   (principle)  — 蓝色框，默认展开
  🥇 课题组经验 (lab_exp)    — 金色框，默认展开，显示作者/时间/审核状态
  💬 相关讨论   (discussion) — 灰色，默认折叠

调用方：main.py，在 render_answer_cards() 之后传入 msg.metadata["qa_trace"]。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# 经验库路径
_BASE_DIR = Path(__file__).resolve().parent.parent
_LAB_EXP_PATH = _BASE_DIR / "knowledge_base" / "lab_experience_kb.json"

# 来源类型配置：(label, icon, expanded, border_color)
_SOURCE_CONFIG: Dict[str, tuple] = {
    "principle":  ("基础原理",   "📚", True,  "#3b82f6"),  # 蓝
    "lab_exp":    ("课题组经验", "🥇", True,  "#f59e0b"),  # 金
    "discussion": ("相关讨论",   "💬", False, "#94a3b8"),  # 灰
}

_LAYER_ORDER = ["principle", "lab_exp", "discussion"]

# 经验库缓存（避免每次渲染重新读文件）
_lab_exp_cache: Optional[Dict[str, Any]] = None


def _load_lab_experiences() -> Dict[str, Dict[str, Any]]:
    """加载课题组经验库，返回 {doc_id: exp_entry} 字典。"""
    global _lab_exp_cache
    if _lab_exp_cache is not None:
        return _lab_exp_cache

    _lab_exp_cache = {}
    if not _LAB_EXP_PATH.exists():
        return _lab_exp_cache

    try:
        data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        for exp in entries:
            exp_id = exp.get("id") or exp.get("doc_id") or ""
            if exp_id:
                _lab_exp_cache[exp_id] = exp
    except Exception:
        pass  # 静默降级
    return _lab_exp_cache


def render_answer_sources(
    qa_trace: Optional[Dict[str, Any]],
    key_prefix: str = "src",
) -> None:
    """渲染三层来源标注。

    Parameters
    ----------
    qa_trace:
        state.last_qa_trace，即 msg.metadata["qa_trace"]。
        若为 None 或 citations 为空，则静默跳过，不渲染任何内容。
    key_prefix:
        Streamlit widget key 前缀，需保证每条消息唯一。
    """
    if not qa_trace:
        return

    citations: List[Dict[str, Any]] = qa_trace.get("citations") or []
    if not citations:
        return

    # 按 source_type 分桶
    buckets: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _LAYER_ORDER}
    for cite in citations:
        stype = cite.get("source_type", "discussion")
        if stype not in buckets:
            stype = "discussion"
        buckets[stype].append(cite)

    # 只渲染有内容的分桶
    filled = [st for st in _LAYER_ORDER if buckets[st]]
    if not filled:
        return

    st.markdown(
        '<p style="font-size:0.78rem;color:#64748b;margin-top:6px;margin-bottom:2px;">📎 回答依据</p>',
        unsafe_allow_html=True,
    )

    for layer_key in filled:
        cites = buckets[layer_key]
        label, icon, default_expanded, border_color = _SOURCE_CONFIG[layer_key]
        _render_source_layer(
            layer_key=layer_key,
            cites=cites,
            label=label,
            icon=icon,
            default_expanded=default_expanded,
            border_color=border_color,
            key=f"{key_prefix}_{layer_key}",
        )


def _render_source_layer(
    layer_key: str,
    cites: List[Dict[str, Any]],
    label: str,
    icon: str,
    default_expanded: bool,
    border_color: str,
    key: str,
) -> None:
    """渲染单个来源层（expander + 卡片列表）。"""
    expander_label = f"{icon} {label}（{len(cites)} 条）"

    with st.expander(expander_label, expanded=default_expanded):
        # 彩色左边框
        st.markdown(
            f'<div style="border-left:3px solid {border_color};padding-left:8px;">',
            unsafe_allow_html=True,
        )
        for i, cite in enumerate(cites):
            _render_cite_item(cite, layer_key, f"{key}_{i}")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_cite_item(cite: Dict[str, Any], layer_key: str, key: str) -> None:
    """渲染单条引用。"""
    ref = cite.get("ref", "")
    doc_id = cite.get("doc_id", "")
    score = cite.get("score", 0.0)
    snippet = cite.get("snippet", "")

    # 格式化 doc_id 显示名
    display_name = _format_doc_name(doc_id, layer_key)

    # 置信度颜色
    if score >= 0.75:
        score_color = "#22c55e"   # 绿
    elif score >= 0.5:
        score_color = "#f59e0b"   # 橙
    else:
        score_color = "#94a3b8"   # 灰

    col_name, col_score = st.columns([5, 1])
    with col_name:
        st.markdown(
            f"<span style='font-size:0.82rem;font-weight:600;'>{ref} {display_name}</span>",
            unsafe_allow_html=True,
        )
    with col_score:
        st.markdown(
            f"<span style='font-size:0.75rem;color:{score_color};'>{score:.2f}</span>",
            unsafe_allow_html=True,
        )

    if snippet:
        st.caption(snippet)

    # 🥇 课题组经验层：显示作者/时间/审核状态
    if layer_key == "lab_exp":
        exp_meta = _get_experience_metadata(doc_id)
        if exp_meta:
            author = exp_meta.get("author", "未知")
            date = exp_meta.get("date", "")
            status = exp_meta.get("status", "pending")

            # 审核状态徽章
            status_badge = {
                "approved": "✅ 已验证",
                "pending": "⚠️ 待审核",
                "rejected": "❌ 已驳回",
            }.get(status, "⚠️ 待审核")

            meta_text = f"来源：{author}"
            if date:
                meta_text += f"（{date[:10]}）"  # 只取日期部分
            meta_text += f" | {status_badge}"

            st.caption(meta_text)


def _get_experience_metadata(doc_id: str) -> Optional[Dict[str, Any]]:
    """从经验库中查找 doc_id 对应的元数据。"""
    exp_dict = _load_lab_experiences()
    return exp_dict.get(doc_id)


def _format_doc_name(doc_id: str, layer_key: str) -> str:
    """将机器 doc_id 转为人类可读名称。"""
    d = doc_id or ""
    # 术语：glossary:CTF → CTF（术语）
    if d.lower().startswith("glossary:"):
        term = d.split(":", 1)[-1]
        return f"{term}（术语）"
    # 站点：cp_01_import → cp_01 导入流程
    if d.lower().startswith("cp_"):
        return d.replace("_", " ").upper()
    # 经验库
    if layer_key == "lab_exp":
        return f"📋 {d}"
    return d or "（未知来源）"
