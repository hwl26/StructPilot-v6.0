"""StructPilot v6.0 — 教学模式渲染层。

展示5要素教学卡片 + 交互测验，帮助用户真正理解每步的"为什么"。
教学进度记录在 st.session_state.teaching_progress。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
_TEACHING_CARDS_PATH = BASE_DIR / "knowledge_base" / "teaching_cards.json"
_QUIZ_BANK_PATH = BASE_DIR / "knowledge_base" / "quiz_bank.json"
_LAB_EXP_PATH = BASE_DIR / "knowledge_base" / "lab_experience_kb.json"


def _load_card(cp_id: str) -> dict:
    try:
        return json.loads(_TEACHING_CARDS_PATH.read_text(encoding="utf-8")).get(cp_id, {})
    except Exception:
        return {}


def _load_quiz(cp_id: str) -> list[dict]:
    try:
        data = json.loads(_QUIZ_BANK_PATH.read_text(encoding="utf-8"))
        return data.get(cp_id, {}).get("questions", [])
    except Exception:
        return []


def _load_lab_exps(cp_id: str) -> list[dict]:
    try:
        data = json.loads(_LAB_EXP_PATH.read_text(encoding="utf-8"))
        return [e for e in data.get("entries", []) if e.get("step") == cp_id]
    except Exception:
        return []


def _init_teaching_state(cp_id: str) -> None:
    if "teaching_progress" not in st.session_state:
        st.session_state.teaching_progress = {}
    if cp_id not in st.session_state.teaching_progress:
        st.session_state.teaching_progress[cp_id] = {
            "cards_read": False,
            "quiz_passed": False,
            "score": 0,
            "attempts": 0,
        }


def _render_teaching_card(cp_id: str, card: dict) -> None:
    """渲染5要素教学卡片。"""
    tc = card.get("teaching_card", {})
    if not tc:
        st.info("📝 本步骤的教学卡片正在编写中，敬请期待。")
        return

    # 要素1：做什么
    what = tc.get("what", "")
    if what:
        with st.container(border=True):
            st.markdown("#### 📚 这一步做什么")
            st.markdown(what)

    # 要素2：关键参数含义
    key_params = tc.get("key_params", [])
    if key_params:
        with st.container(border=True):
            st.markdown("#### 🔑 关键参数含义")
            for p in key_params:
                name = p.get("name", "")
                meaning = p.get("meaning", "")
                rng = p.get("range", "")
                st.markdown(f"**`{name}`**：{meaning}")
                if rng:
                    st.caption(f"常见范围：{rng}")
                st.markdown("")

    # 要素3：常见设置范围（表格）
    ranges = tc.get("common_ranges", [])
    if ranges:
        with st.container(border=True):
            st.markdown("#### 📊 常见设置范围")
            import pandas as pd
            try:
                df = pd.DataFrame(ranges)
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception:
                for row in ranges:
                    st.markdown(f"- {row}")

    # 要素4：常见问题（优先课题组经验）
    lab_exps = _load_lab_exps(cp_id)
    common_problems = tc.get("common_problems", [])
    if lab_exps or common_problems:
        with st.container(border=True):
            st.markdown("#### ⚠️ 常见问题 & 课题组经验")
            if lab_exps:
                for exp in lab_exps[:3]:
                    badge = "🥇 课题组经验" if exp.get("status") == "approved" else "⚠️ 待验证经验"
                    with st.expander(f"{badge}：{exp.get('title', '')}", expanded=False):
                        symptoms = exp.get("symptoms", [])
                        if isinstance(symptoms, list):
                            st.markdown("**症状**：" + "；".join(symptoms))
                        st.markdown(f"**解决**：{exp.get('solution', '')}")
                        st.caption(f"{exp.get('author', '')} · {exp.get('date', '')}")
            if common_problems:
                st.markdown("**官方文档提示：**")
                for prob in common_problems:
                    st.markdown(f"- {prob}")

    # 要素5：判断标准
    success_criteria = tc.get("success_criteria", "")
    if success_criteria:
        with st.container(border=True):
            st.markdown("#### 🎯 判断标准（如何知道这步做对了）")
            st.success(success_criteria)

    # 标记卡片已读
    st.session_state.teaching_progress[cp_id]["cards_read"] = True


def _render_quiz(cp_id: str, questions: list[dict]) -> None:
    """渲染交互测验，逐题展示，记录分数。"""
    if not questions:
        st.info("🧪 本步骤测验题目正在编写中。")
        if st.button("✅ 跳过测验，标记为已学习", key=f"quiz_skip_{cp_id}"):
            st.session_state.teaching_progress[cp_id]["quiz_passed"] = True
        return

    prog = st.session_state.teaching_progress[cp_id]
    q_idx_key = f"_quiz_idx_{cp_id}"
    answers_key = f"_quiz_answers_{cp_id}"
    done_key = f"_quiz_done_{cp_id}"

    if q_idx_key not in st.session_state:
        st.session_state[q_idx_key] = 0
    if answers_key not in st.session_state:
        st.session_state[answers_key] = {}
    if done_key not in st.session_state:
        st.session_state[done_key] = False

    total = len(questions)
    idx = st.session_state[q_idx_key]

    # 进度条
    st.progress((idx) / total, text=f"第 {min(idx + 1, total)}/{total} 题")

    if st.session_state[done_key]:
        # 显示最终结果
        correct = sum(
            1 for i, q in enumerate(questions)
            if st.session_state[answers_key].get(i) == q.get("correct")
        )
        prog["score"] = correct
        prog["attempts"] = prog.get("attempts", 0) + 1

        if correct >= len(questions) * 0.67:
            prog["quiz_passed"] = True
            st.success(f"🎉 测验通过！答对 {correct}/{total} 题")
            if st.button("⚙️ 切换到高级模式使用更多功能", key=f"quiz_to_expert_{cp_id}"):
                st.session_state.app_mode = "expert"
                st.rerun()
        else:
            st.warning(f"答对 {correct}/{total}，建议重读卡片后再试（至少需要 {int(len(questions)*0.67)+1} 题正确）")
            if st.button("🔁 重新测验", key=f"quiz_retry_{cp_id}"):
                st.session_state[q_idx_key] = 0
                st.session_state[answers_key] = {}
                st.session_state[done_key] = False
                st.rerun()
        return

    # 显示当前题
    if idx < total:
        q = questions[idx]
        st.markdown(f"**Q{idx+1}：{q.get('question', '')}**")
        opts = q.get("options", [])
        selected = st.radio(
            "选择答案", opts,
            key=f"quiz_radio_{cp_id}_{idx}",
            label_visibility="collapsed",
        )
        if st.button("确认", key=f"quiz_confirm_{cp_id}_{idx}"):
            chosen_idx = opts.index(selected) if selected in opts else -1
            st.session_state[answers_key][idx] = chosen_idx
            correct_idx = q.get("correct", -1)
            if chosen_idx == correct_idx:
                st.toast("✅ 正确！")
            else:
                st.toast(f"❌ 正确答案：{opts[correct_idx] if 0 <= correct_idx < len(opts) else '?'}")
            if idx < total - 1:
                st.session_state[q_idx_key] = idx + 1
            else:
                st.session_state[done_key] = True
            # 显示解释
            explanation = q.get("explanation", "")
            if explanation:
                st.info(explanation)
            st.rerun()


def render_teaching_view(
    current_cp: dict,
    state: Any,
    app: Any,
) -> None:
    """教学模式主渲染函数。"""
    cp_id = current_cp.get("checkpoint_id", "")
    cp_cn = current_cp.get("checkpoint_cn", current_cp.get("checkpoint_name", ""))
    order = current_cp.get("order", 0)

    _init_teaching_state(cp_id)
    prog = st.session_state.teaching_progress[cp_id]

    card = _load_card(cp_id)
    questions = _load_quiz(cp_id)

    # ── 顶部标题 + 状态徽章 ──────────────────────────────────
    badges = ""
    if prog.get("cards_read"):
        badges += '<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;font-size:0.78rem;margin-right:4px;">✓ 卡片已读</span>'
    if prog.get("quiz_passed"):
        badges += '<span style="background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:10px;font-size:0.78rem;">🎓 测验通过</span>'

    st.markdown(
        f"<h3 style='margin-bottom:4px;'>🎓 第{order}步原理学习：{cp_cn}</h3>"
        f"<div style='margin-bottom:8px;'>{badges}</div>",
        unsafe_allow_html=True,
    )

    # ── Tab：卡片 / 测验 / 课题组经验 ────────────────────────
    tab_card, tab_quiz, tab_lab = st.tabs(["💡 原理卡片", "✍️ 知识测验", "🥇 课题组经验"])

    with tab_card:
        _render_teaching_card(cp_id, card)

    with tab_quiz:
        if not prog.get("cards_read"):
            st.warning("建议先阅读原理卡片，再开始测验。")
        _render_quiz(cp_id, questions)

    with tab_lab:
        from components.experience_card import render_experience_card

        lab_exps = _load_lab_exps(cp_id)
        if lab_exps:
            for exp in lab_exps:
                render_experience_card(exp, expanded=False)
        else:
            st.info("本步骤暂无课题组经验记录。\n\n遇到问题后可通过「贡献经验」按钮添加。")

        # ✨ GitHub Discussions 社区入口
        st.markdown("---")
        st.markdown("### 💬 课题组论坛（GitHub Discussions）")
        st.markdown(
            "**在社区论坛中：**\n"
            "- 提问：遇到问题随时发帖求助\n"
            "- 分享：把踩坑经验发出来帮助他人\n"
            "- 讨论：和其他课题组交流技巧\n"
            "- 投票：给有用的经验点赞👍"
        )
        discussions_url = "https://github.com/hwl26/StructPilot-v6.0/discussions"
        st.link_button(
            "🌐 打开课题组论坛（新窗口）",
            url=discussions_url,
            use_container_width=True,
            help="管理员审核后的经验会被收录到正式知识库",
        )
        st.caption("💡 Tip：未来将直接在此页面嵌入 Discussions，无需跳转")


    # ── 底部导航 ─────────────────────────────────────────────
    st.markdown("---")
    col_back, col_op = st.columns(2)
    with col_back:
        if st.button("🔧 回到操作", use_container_width=True, key="teach_to_beginner"):
            st.session_state.app_mode = "beginner"
            st.rerun()
    with col_op:
        if st.button("⚙️ 进入高级模式", use_container_width=True, key="teach_to_expert"):
            st.session_state.app_mode = "expert"
            st.rerun()

    # 智能滚动锚点：供 inject_smart_scroll() 定位聊天底部
    st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
