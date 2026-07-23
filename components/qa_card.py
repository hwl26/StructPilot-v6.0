"""StructPilot v6.0 — 质检卡片组件。

evaluate_qa()：基于规则判断当前步骤的质检状态
render_qa_card()：统一质控渲染入口（状态卡片 / 清单 / 分组清单）
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, List

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_QC_STANDARD_PATH = BASE_DIR / "knowledge_base" / "qc_standard.json"
_TEACHING_CARDS_PATH = BASE_DIR / "knowledge_base" / "teaching_cards.json"

# 统一颜色 / 图标规范（pass/warn/fail 为主三态，pending=待检查，info=提示）
_QC_STYLES = {
    "pass":    {"icon": "✅", "color": "#10b981", "bg": "#ecfdf5", "label": "质检通过"},
    "warn":    {"icon": "⚠️", "color": "#f59e0b", "bg": "#fef3c7", "label": "需要注意"},
    "fail":    {"icon": "❌", "color": "#ef4444", "bg": "#fef2f2", "label": "建议重做"},
    "pending": {"icon": "☐", "color": "#6b7280", "bg": "#f9fafb", "label": "待检查"},
    "info":    {"icon": "ℹ️", "color": "#3b82f6", "bg": "#eff6ff", "label": "质检提示"},
}
_GROUP_KEYS = ("fail", "warn", "pass", "pending")


def _load_qc_rules(cp_id: str) -> list[dict]:
    """从 teaching_cards.json 加载该步骤的质检规则。"""
    try:
        data = json.loads(_TEACHING_CARDS_PATH.read_text(encoding="utf-8"))
        return data.get(cp_id, {}).get("quality_check", {}).get("rules", [])
    except Exception:
        return []


def evaluate_qa(cp_id: str, card: dict, session_state: Any) -> dict:
    """评估当前步骤质检状态。

    返回 dict：
        status: "pass" | "warn" | "fail" | "info"
        message: str
        suggestions: list[str]
    """
    rules = _load_qc_rules(cp_id)

    # 默认：给出通用指导
    success = card.get("teaching_card", {}).get("success_criteria", "")
    return {
        "status": "info",
        "message": success or "请对照软件输出，确认结果符合预期后继续。",
        "suggestions": ["检查软件输出日志是否有报错", "对照本步骤判断标准确认结果质量"],
    }


def _normalize_status(status: Any) -> str:
    """归一化状态字符串到 _QC_STYLES 的键。"""
    if isinstance(status, str) and status.lower() in _QC_STYLES:
        return status.lower()
    return "info"


def _normalize_list_item(item: Any) -> tuple[str, str, str]:
    """归一化清单项 -> (text, status, threshold)。

    兼容 answer_cards 的 items 格式：
        {"check"/"item"/"text": str, "passed": True|False|None, "threshold"/"criterion": str}
        {"item": str, "status": "pass|warn|fail|pending"}
        "纯字符串"（默认 pending）
    """
    if isinstance(item, dict):
        text = item.get("check") or item.get("item") or item.get("text") or ""
        threshold = item.get("threshold") or item.get("criterion") or ""
        if item.get("status"):
            status = _normalize_status(item["status"])
        else:
            passed = item.get("passed")
            if passed is True:
                status = "pass"
            elif passed is False:
                status = "fail"
            else:
                status = "pending"
        return str(text), status, str(threshold)
    return str(item), "pending", ""


def _render_status_banner(status: str, message: str, suggestions: list) -> None:
    """渲染单个状态横幅（统一颜色 / 图标）。"""
    style = _QC_STYLES.get(status, _QC_STYLES["info"])
    label = style["label"]
    parts: list[str] = []
    if label:
        parts.append(f"<strong>{style['icon']} {html.escape(label)}</strong>")
    if message:
        parts.append(f"<div style=\"margin-top:4px;\">{html.escape(message)}</div>")
    body = "".join(parts) or f"<strong>{style['icon']}</strong>"
    block = (
        f"<div style=\"background:{style['bg']};border-left:4px solid {style['color']};"
        f"border-radius:6px;padding:10px 14px;margin:6px 0;color:{style['color']};\">"
        f"{body}</div>"
    )
    st.markdown(block, unsafe_allow_html=True)
    if suggestions:
        heading = "排查步骤" if status == "fail" else "建议"
        st.markdown(f"**{heading}：**")
        for s in suggestions:
            st.markdown(f"- {s}")


def _render_checklist(items: list) -> None:
    """渲染清单（每项一行，统一颜色 / 图标）。"""
    for item in items:
        text, status, threshold = _normalize_list_item(item)
        style = _QC_STYLES.get(status, _QC_STYLES["pending"])
        threshold_html = ""
        if threshold:
            threshold_html = (
                f" <span style=\"color:#6b7280;font-size:0.85em;\">"
                f"(标准: {html.escape(threshold)})</span>"
            )
        block = (
            f"<div style=\"background:{style['bg']};border-left:3px solid {style['color']};"
            f"border-radius:4px;padding:6px 10px;margin:4px 0;color:{style['color']};\">"
            f"{style['icon']} {html.escape(text)}{threshold_html}</div>"
        )
        st.markdown(block, unsafe_allow_html=True)


def _render_grouped(groups: dict) -> None:
    """渲染分组清单 {"pass": [...], "warn": [...], "fail": [...], "pending": [...]}。"""
    for group in _GROUP_KEYS:
        items = groups.get(group) or []
        if not items:
            continue
        style = _QC_STYLES.get(group, _QC_STYLES["pending"])
        label = style["label"] or group
        st.markdown(f"**{style['icon']} {label}（{len(items)}）**")
        for raw in items:
            text, _, threshold = _normalize_list_item(raw)
            threshold_html = ""
            if threshold:
                threshold_html = (
                    f" <span style=\"color:#6b7280;font-size:0.85em;\">"
                    f"(标准: {html.escape(threshold)})</span>"
                )
            block = (
                f"<div style=\"background:{style['bg']};border-left:3px solid {style['color']};"
                f"border-radius:4px;padding:6px 10px;margin:4px 0;color:{style['color']};\">"
                f"{style['icon']} {html.escape(text)}{threshold_html}</div>"
            )
            st.markdown(block, unsafe_allow_html=True)


def render_qa_card(
    result: Any = None,
    *,
    message: str | None = None,
    suggestions: list | None = None,
    content: str = "",
    key: str | None = None,
) -> None:
    """统一质控渲染入口（唯一实现）。

    支持多种输入格式：
        1. 状态卡片 dict（向后兼容原 render_qa_card(result)）：
            {"status": "pass|warn|fail|info", "message": str, "suggestions": list}
        2. 分组清单 dict：
            {"pass": [...], "warn": [...], "fail": [...], "pending": [...]}
        3. 清单 list（兼容 answer_cards 的 items）：
            [{"item": "...", "status": "pass|warn|fail|pending", "threshold": "..."}, ...]
            或 [{"check"/"item"/"text": ..., "passed": True|False|None, "threshold"/"criterion": ...}, ...]
        4. 字符串清单 list[str]：默认全部 pending（待检查）

    关键字参数：
        message     状态卡片消息（覆盖 result["message"]）
        suggestions 状态卡片建议列表（覆盖 result["suggestions"]）
        content     清单前的说明文本（仅清单 / 分组模式渲染）
        key         组件 key（预留，当前未使用）
    """
    # 2) 分组清单 dict
    if isinstance(result, dict) and any(k in result for k in _GROUP_KEYS):
        if content:
            st.markdown(content)
        _render_grouped(result)
        return

    # 1) 状态卡片 dict
    if isinstance(result, dict):
        status = _normalize_status(result.get("status", "info"))
        msg = message if message is not None else result.get("message", "")
        sugg = suggestions if suggestions is not None else result.get("suggestions", [])
        if content:
            st.markdown(content)
        _render_status_banner(status, str(msg), list(sugg or []))
        return

    # 3/4) 清单 list
    if isinstance(result, list):
        if content:
            st.markdown(content)
        if not result:
            return
        _render_checklist(result)
        return

    # 仅显式参数（无 result）
    if content:
        st.markdown(content)
    if message is not None:
        _render_status_banner("info", str(message), list(suggestions or []))
