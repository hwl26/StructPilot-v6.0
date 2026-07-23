"""StructPilot v6.0 — 入门模式渲染层。

极简 SOP 引导：每步一屏、一键应用推荐参数、质检闭环。
底层数据不变，只改视图呈现方式。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_TEACHING_CARDS_PATH = BASE_DIR / "knowledge_base" / "teaching_cards.json"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def _load_teaching_card(cp_id: str) -> dict:
    try:
        data = json.loads(_TEACHING_CARDS_PATH.read_text(encoding="utf-8"))
        return data.get(cp_id, {})
    except Exception:
        return {}


def _load_lab_experiences(cp_id: str) -> list[dict]:
    try:
        data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        return [e for e in data.get("entries", []) if e.get("step") == cp_id]
    except Exception:
        return []


def _render_sop_instructions(cp_id: str, card: dict) -> None:
    """渲染傻瓜式操作指令区块。"""
    instructions = card.get("beginner_instructions", [])
    if not instructions:
        instructions = [
            f"① 确认上一步已完成，软件内已有 {cp_id} 对应的输出",
            "② 按软件默认流程建立作业，保持推荐参数不变",
            "③ 点击 Continue / Queue Job 提交作业",
            "④ 等待运行完成后，点击下方「检查结果」",
        ]
    st.markdown("**操作指令**")
    for instr in instructions:
        st.markdown(f"- {instr}")


def _render_beginner_params(params: list[dict]) -> None:
    """入门模式参数展示：只显示被标记为需要关注的参数，其余折叠。"""
    critical = [p for p in params if p.get("beginner_highlight")]
    others = [p for p in params if not p.get("beginner_highlight")]

    if critical:
        st.markdown("**需要关注的参数**")
        for p in critical:
            name = p.get("name", "")
            rec = p.get("recommended_value", p.get("default_value", "—"))
            tip = p.get("beginner_tip", "")
            st.markdown(
                f"- `{name}` → **{rec}**" + (f"（{tip}）" if tip else "")
            )

    if others:
        with st.expander(f"其余 {len(others)} 个参数（保持默认即可）", expanded=False):
            for p in others:
                name = p.get("name", "")
                default = p.get("default_value", "—")
                st.markdown(f"- `{name}` = {default}")


def _render_qa_result_inline(cp_id: str, card: dict, run_command_fn: Callable) -> None:
    """执行质检并展示结果卡片。"""
    from components.qa_card import render_qa_card, evaluate_qa

    result = evaluate_qa(cp_id, card, st.session_state)
    render_qa_card(result)

    if result.get("status") == "fail":
        exps = _load_lab_experiences(cp_id)
        if exps:
            st.markdown("---")
            st.markdown("🥇 **课题组有人遇到过类似问题：**")
            for exp in exps[:2]:
                with st.expander(f"📌 {exp.get('title', '经验条目')}", expanded=True):
                    st.markdown(f"**症状**：{exp.get('symptoms_text', '')}")
                    st.markdown(f"**解决**：{exp.get('solution', '')}")
                    badge = "✅ 已验证" if exp.get("status") == "approved" else "⚠️ 待验证"
                    st.caption(f"{badge} · {exp.get('author', '')} · {exp.get('date', '')}")

        if st.button("🎓 去教学模式了解原理", key="beginner_to_teaching"):
            st.session_state.app_mode = "teaching"
            st.rerun()


def render_beginner_view(
    current_cp: dict,
    state: Any,
    app: Any,
    run_command_fn: Callable,
) -> None:
    """入门模式主渲染函数。

    首次使用时展示需求问答，完成后才进入实际流程。
    """
    from components.onboarding_v2 import render_onboarding_dialog

    # ── 首次使用检测：展示需求问答 ──────────────────────────────
    if not st.session_state.get("onboarding_completed", False):
        if render_onboarding_dialog():
            st.rerun()  # 完成问答后刷新页面
        return  # 问答未完成时阻止后续内容渲染

    # ── 问答已完成，检查是否需要跳过当前步骤 ────────────────────
    cp_id = current_cp.get("checkpoint_id", "")
    workflow = st.session_state.get("recommended_workflow", {})
    skip_steps = workflow.get("skip_steps", [])

    if cp_id in skip_steps:
        # 当前步骤在跳过列表中，显示跳过提示
        st.info(
            f"**✓ 此步骤已根据你的需求自动跳过**  \n"
            f"你的目标是「{st.session_state.user_profile.get('goal', '')}」，"
            f"本步骤不在推荐流程中。"
        )
        if st.button("➡ 继续下一步", use_container_width=True, type="primary"):
            run_command_fn("跳过")
            st.rerun()
        return

    # ── 正常步骤渲染 ──────────────────────────────────────────
    cp_cn = current_cp.get("checkpoint_cn", current_cp.get("checkpoint_name", "未知步骤"))
    order = current_cp.get("order", 0)
    phase = current_cp.get("phase", "")

    card = _load_teaching_card(cp_id)

    # ── 步骤标题 ──────────────────────────────────────────────
    st.markdown(
        f"<h3 style='margin-bottom:4px;'>📌 第{order}步：{cp_cn}</h3>"
        f"<span style='color:#64748b;font-size:0.85rem;'>阶段：{phase}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── 做什么（What）─────────────────────────────────────────
    what_text = card.get("what", current_cp.get("description", "按软件向导完成本步骤操作。"))
    st.info(f"**这一步做什么**：{what_text}")

    # ── 操作指令 ──────────────────────────────────────────────
    _render_sop_instructions(cp_id, card)

    # ── 主截图（仅第一张，带基础热点） ────────────────────────
    from ui.components import render_stage_workspace

    try:
        render_stage_workspace(
            current_cp,
            state.software,
            state,
            app,
            on_switch=None,
            key_prefix="bg_ws",
        )
    except Exception as exc:
        st.error(f"截图加载失败：{exc}")

    # ── 参数面板（简化版） ─────────────────────────────────────
    raw_tabs = current_cp.get("tabs", [])
    all_params: list[dict] = []
    for tab in raw_tabs:
        all_params.extend(tab.get("parameters", []))
    if all_params:
        _render_beginner_params(all_params)

    st.markdown("---")

    # ── 操作按钮区 ─────────────────────────────────────────────
    col_check, col_next, col_teach = st.columns([1.5, 1.5, 1])
    with col_check:
        if st.button("✅ 检查结果", use_container_width=True, type="primary",
                     key="bg_check_result"):
            st.session_state[f"_bg_show_qa_{cp_id}"] = True

    with col_next:
        if st.button("➡ 进入下一步", use_container_width=True,
                     key="bg_next_step"):
            run_command_fn("完成")
            st.rerun()

    with col_teach:
        if st.button("🎓 学习原理", use_container_width=True,
                     key="bg_to_teaching"):
            st.session_state.app_mode = "teaching"
            st.rerun()

    # ── 质检结果（懒渲染，点击后出现） ───────────────────────
    if st.session_state.get(f"_bg_show_qa_{cp_id}"):
        st.markdown("---")
        _render_qa_result_inline(cp_id, card, run_command_fn)

    # ── 快速问答（悬浮式，保留原有能力） ─────────────────────
    with st.expander("💬 有问题？问 StructPilot", expanded=False):
        q = st.text_input("输入问题", key="bg_quick_q", label_visibility="collapsed",
                          placeholder=f"例：{cp_cn} 时参数怎么设？")
        if st.button("提问", key="bg_ask"):
            if q.strip():
                run_command_fn(q)
                st.rerun()

    # 智能滚动锚点：供 inject_smart_scroll() 定位聊天底部
    st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
