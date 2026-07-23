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
    """执行质检并展示结果卡片（✨ 含智能经验推送）。"""
    from components.qa_card import render_qa_card, evaluate_qa
    from components.experience_card import render_experience_card
    from utils.experience_matcher import find_similar_experiences

    result = evaluate_qa(cp_id, card, st.session_state)
    render_qa_card(result)

    # ✨ 质检失败时，智能推送相似经验
    if result.get("status") == "fail":
        # 构建查询：质检问题描述
        issues = result.get("issues", "")
        query_text = f"{cp_id} {issues}"

        # 查找相似经验（基于关键词匹配）
        similar_exps = find_similar_experiences(
            query=query_text,
            current_step=cp_id,
            top_k=3,
            min_similarity=0.15,  # 较低阈值，确保有推荐
        )

        if similar_exps:
            st.markdown("---")
            st.markdown("### 🥇 课题组有人遇到过类似问题")
            st.caption(f"为你匹配到 {len(similar_exps)} 条相关经验：")

            for exp, similarity in similar_exps[:2]:  # 最多显示2条
                render_experience_card(exp, expanded=True)

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
    # ── 首次使用检测：展示需求问答 ──────────────────────────────
    if not st.session_state.get("onboarding_completed", False):
        # 问卷模式：v3=对话式（默认）/ v2=快速选择
        onboarding_mode = st.session_state.get("_onboarding_mode", "v3")

        if onboarding_mode == "v3":
            from components.onboarding_v3 import render_conversational_onboarding
            if render_conversational_onboarding(app):
                st.rerun()  # 完成问答后刷新页面
        else:
            from components.onboarding_v2 import render_onboarding_dialog
            # 提供切回对话式的入口
            if st.button("💬 改用对话式规划", key="switch_to_v3"):
                st.session_state["_onboarding_mode"] = "v3"
                st.rerun()
            if render_onboarding_dialog():
                st.rerun()
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
                st.session_state["_bg_qa_visible"] = True
                # 入门模式显式传 teaching profile，确保 LLM 润色
                run_command_fn(q, response_profile="teaching")
                st.rerun()

    # ── 最近问答展示（点击「提问」后展开，限高滚动） ───────────
    if st.session_state.get("_bg_qa_visible"):
        st.markdown("---")
        st.markdown("#### 💬 最近对话")

        # 只显示最近 2 轮（最多 4 条消息：Q→A→Q→A）
        messages = state.messages[-4:] if hasattr(state, "messages") else []

        # 固定高度容器 + 自动滚动，避免挤占页面
        with st.container():
            # 使用 HTML + CSS 实现限高滚动（Streamlit 原生 container 不支持高度限制）
            chat_html = '<div style="max-height:400px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px;padding:12px;background:#fafafa;">'
            for msg in messages:
                role_icon = "👤" if msg.role == "user" else "🤖"
                role_label = "你" if msg.role == "user" else "StructPilot"
                role_color = "#3b82f6" if msg.role == "user" else "#10b981"
                chat_html += f'<div style="margin-bottom:12px;"><strong style="color:{role_color};">{role_icon} {role_label}</strong><br>'
                # 简单转义防止 HTML 注入（生产环境应使用更严格的 sanitizer）
                content = str(msg.content).replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                chat_html += f'<span style="color:#1e293b;">{content}</span></div>'
            chat_html += '</div>'
            st.markdown(chat_html, unsafe_allow_html=True)

        col_hide, col_tip = st.columns([1, 3])
        with col_hide:
            if st.button("收起对话", key="bg_hide_qa"):
                st.session_state["_bg_qa_visible"] = False
                st.rerun()
        with col_tip:
            # LLM 降级提示（仅当最新回复是规则回复时）
            if messages:
                last_msg = messages[-1]
                if last_msg.role == "assistant":
                    trace = getattr(last_msg, "metadata", {}).get("qa_trace", {})
                    if trace.get("fallback") and "llm" in str(trace.get("fallback_reason", "")):
                        st.caption("⚠️ LLM 未启用或调用失败，已使用规则回复。前往「高级模式·设置」配置 API。")

    # 智能滚动锚点：供 inject_smart_scroll() 定位聊天底部
    st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
