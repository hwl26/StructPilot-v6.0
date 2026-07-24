"""StructPilot v6.0 — 对话式需求问答（Onboarding v3）。

区别于 v2 的卡片式选择，v3 让小白用自然语言描述项目背景和实验目的，
由 LLM 抽取结构化画像（样品类型/目标/设备/经验），LLM 不可用时降级为
关键词规则解析。最终复用 v2 的 _generate_workflow_recommendation 生成路线，
并用 Graphviz 灵动展示。

设计原则：只新增能力，不改动 v2。用户可在两种问卷间自由选择。
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

# 复用 v2 的工作流推荐逻辑，避免重复实现规则映射
from components.onboarding_v2 import _generate_workflow_recommendation


# --------------------------------------------------------------------------- #
# 规则兜底：从自然语言中抽取画像（LLM 不可用时）
# --------------------------------------------------------------------------- #
_SAMPLE_KEYWORDS = {
    "小型蛋白/复合物": ["小蛋白", "小型", "单体", "小分子", "<150", "100kda", "50kda"],
    "中等蛋白复合物": ["膜蛋白", "gpcr", "trpv", "离子通道", "受体", "中等", "150-500", "200kda", "300kda"],
    "大型复合物": ["核糖体", "剪接体", "大型", "复合物", ">500", "megadalton", "蛋白酶体"],
    "病毒/高对称颗粒": ["病毒", "衣壳", "capsid", "virus", "对称", "icosahedral", "二十面体"],
}

_GOAL_KEYWORDS = {
    "3D重构": ["高分辨", "三维", "3d", "结构解析", "原子模型", "nature", "science", "重构", "重建"],
    "2D分类": ["2d", "二维", "分类", "筛选状态", "看看颗粒", "初步结构"],
    "质检": ["质检", "质量", "筛选数据", "看数据好不好", "评估", "初筛", "quality"],
}

_MICROSCOPE_KEYWORDS = {
    "Krios 300kV": ["krios", "300", "titan"],
    "Arctica 200kV": ["arctica", "200", "talos", "glacios"],
}

_RESOLUTION_KEYWORDS = {
    "高分辨": ["高分辨", "原子", "<4", "3.5", "3å", "近原子"],
    "粗筛": ["粗", "初步", "快速", "看看", ">10", "低分辨"],
    "中等": ["中等", "5-10", "一般"],
}


def _rule_extract_profile(text: str) -> Dict[str, str]:
    """关键词规则抽取（LLM 兜底）。返回可能不完整的画像。"""
    low = text.lower()
    profile: Dict[str, str] = {}

    for label, kws in _SAMPLE_KEYWORDS.items():
        if any(k in low for k in kws):
            profile["sample_type"] = label
            break

    for label, kws in _GOAL_KEYWORDS.items():
        if any(k in low for k in kws):
            profile["goal"] = label
            break

    for label, kws in _MICROSCOPE_KEYWORDS.items():
        if any(k in low for k in kws):
            profile["microscope"] = label
            break

    for label, kws in _RESOLUTION_KEYWORDS.items():
        if any(k in low for k in kws):
            profile["resolution_target"] = label
            break

    # 经验判断
    if any(k in low for k in ["新手", "第一次", "不懂", "小白", "没用过", "初学"]):
        profile["experience"] = "新手"
    elif any(k in low for k in ["用过", "有经验", "熟悉", "做过"]):
        profile["experience"] = "有经验"

    return profile


_LLM_SYSTEM_PROMPT = """你是冷冻电镜（cryo-EM）单颗粒数据处理流程规划助手。
用户会用自然语言描述他们的项目背景和实验目的。请从中抽取结构化信息，返回 JSON。

字段规则（无法判断的字段返回空字符串）：
- sample_type: 样品尺度，从以下四选一或空：
    "小型蛋白/复合物"(<150 kDa)、"中等蛋白复合物"(150-500 kDa，如膜蛋白/GPCR/离子通道)、
    "大型复合物"(>500 kDa，如核糖体)、"病毒/高对称颗粒"
- goal: 目标，从以下三选一或空：
    "质检"(只想看数据质量)、"2D分类"(想筛选颗粒/看初步结构)、"3D重构"(想解出高分辨率三维结构)
- microscope: 设备，"Krios 300kV" 或 "Arctica 200kV" 或空
- resolution_target: "高分辨" / "中等" / "粗筛" 或空
- experience: "新手" 或 "有经验" 或空
- protein_name: 用户提到的具体蛋白名（如 TRPV1），没有则空
- notes: 一句话总结你对用户情况的理解（中文）

只返回 JSON，不要多余文字。示例：
{"sample_type":"中等蛋白复合物","goal":"3D重构","microscope":"","resolution_target":"高分辨","experience":"有经验","protein_name":"TRPV1","notes":"研究TRPV1膜蛋白，已有数据，想冲高分辨率结构"}"""


def _llm_extract_profile(text: str, app: Any) -> Dict[str, str] | None:
    """LLM 抽取画像。app.llm 不可用时返回 None。"""
    llm = getattr(app, "llm", None)
    if llm is None:
        return None
    result = llm.extract_json(_LLM_SYSTEM_PROMPT, text)
    if not isinstance(result, dict):
        return None
    # 只保留字符串字段
    return {k: str(v) for k, v in result.items() if v}


def _init_state() -> None:
    if "onboarding_completed" not in st.session_state:
        st.session_state.onboarding_completed = False
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {}
    if "recommended_workflow" not in st.session_state:
        st.session_state.recommended_workflow = {}
    st.session_state.setdefault("_v3_extracted", None)


def render_conversational_onboarding(app: Any = None) -> bool:
    """渲染对话式问答。

    Returns
    -------
    bool
        用户是否完成并确认了路线。
    """
    _init_state()

    st.markdown(
        "<h3 style='margin-bottom:2px;'>👋 你好，我是 StructPilot</h3>"
        "<p style='color:#64748b;margin-top:0;'>用大白话跟我聊聊你的项目就行，我来帮你规划冷冻电镜数据处理路线。</p>",
        unsafe_allow_html=True,
    )

    llm_ready = bool(getattr(getattr(app, "llm", None), "enabled", False))
    if llm_ready:
        st.caption("🤖 AI 理解模式已启用，随便怎么描述都行")
    else:
        st.caption("📝 规则解析模式（未配置 AI）：请尽量提到样品类型、目标、设备等关键词")

    # ── 输入区 ──────────────────────────────────────────────
    example = (
        "例：我在做 TRPV1 离子通道，是膜蛋白。已经在 Krios 上拍了大概 5000 张 movies，"
        "想解出高分辨率结构。之前用过一次 RELION，但很多参数不太懂。"
    )

    # 语音输入（复用高级模式的 LLM Whisper 配置）
    audio_ready = bool(getattr(getattr(app, "llm", None), "audio_enabled", False))
    if audio_ready:
        with st.expander("🎤 用语音描述（点击展开录音）", expanded=False):
            st.caption("点击麦克风按钮开始录音，录音完成后会自动识别并填入下方输入框。")

            # 使用 Streamlit 原生 audio_input（更稳定）
            audio_bytes = st.audio_input("录音", key="_v3_audio_input", label_visibility="collapsed")

            if audio_bytes:
                with st.spinner("正在识别语音..."):
                    import tempfile
                    import os
                    # st.audio_input 返回 UploadedFile 对象
                    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                    try:
                        os.write(tmp_fd, audio_bytes.read())
                        os.close(tmp_fd)
                        transcript = app.llm.transcribe_audio(tmp_path, language="zh")
                        if transcript.strip():
                            st.session_state["_v3_input"] = transcript
                            st.success(f"✓ 已识别 {len(transcript)} 字")
                            st.rerun()
                        else:
                            st.warning("识别结果为空，请重新录音或检查麦克风")
                    except Exception as exc:
                        st.error(f"识别失败：{exc}\n\n请检查：\n1. 高级模式是否配置了 Audio Model\n2. API Key 是否有效\n3. 麦克风权限是否授予")
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
    else:
        st.caption("💡 提示：配置 LLM 的 Audio Model 后可启用语音输入（在高级模式·设置中配置）")

    user_text = st.text_area(
        "描述你的项目背景和目标",
        height=140,
        placeholder=example,
        key="_v3_input",
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        analyze = st.button("🔍 帮我规划路线", use_container_width=True, type="primary")
    with col_b:
        if st.button("📋 改用快速选择问卷", use_container_width=True):
            st.session_state["_onboarding_mode"] = "v2"
            st.rerun()

    # ── 分析用户输入 ────────────────────────────────────────
    if analyze:
        if not user_text.strip():
            st.warning("先简单描述一下你的项目吧～")
            return False

        with st.spinner("正在理解你的需求..."):
            profile = None
            if llm_ready:
                profile = _llm_extract_profile(user_text, app)
            # LLM 不可用或失败 → 规则兜底
            if not profile:
                profile = _rule_extract_profile(user_text)
                profile.setdefault("notes", "（规则解析）已根据关键词识别你的需求")

        st.session_state["_v3_extracted"] = profile

    # ── 展示抽取结果 + 路线 ─────────────────────────────────
    extracted = st.session_state.get("_v3_extracted")
    if extracted:
        st.markdown("---")
        _render_understanding(extracted)

        # 生成工作流推荐（复用 v2 逻辑）
        workflow = _generate_workflow_recommendation(extracted)

        st.markdown("### 🗺️ 为你规划的处理路线")
        st.info(workflow.get("reason", ""))

        _render_workflow_graph(workflow, app)

        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅ 确认，开始使用", use_container_width=True, type="primary"):
                st.session_state.user_profile = extracted
                st.session_state.recommended_workflow = workflow
                st.session_state.onboarding_completed = True
                st.session_state["_v3_extracted"] = None
                return True
        with col2:
            if st.button("🔄 重新描述", use_container_width=True):
                st.session_state["_v3_extracted"] = None
                st.rerun()

    return False


# 各画像字段的可选值（与 _generate_workflow_recommendation 的匹配逻辑一致）
_FIELD_OPTIONS = {
    "sample_type": ["", "小型蛋白/复合物", "中等蛋白复合物", "大型复合物", "病毒/高对称颗粒"],
    "goal": ["", "质检", "2D分类", "3D重构"],
    "microscope": ["", "Krios 300kV", "Arctica 200kV"],
    "resolution_target": ["", "高分辨", "中等", "粗筛"],
    "experience": ["", "新手", "有经验"],
}


def _render_understanding(profile: Dict[str, str]) -> None:
    """展示并允许就地编辑 AI/规则对用户需求的理解。

    编辑后的值直接写回传入的 profile（即 session_state["_v3_extracted"] 引用），
    使重新生成的路线反映用户修正。
    """
    notes = profile.get("notes", "")

    col_head, col_toggle = st.columns([3, 1])
    with col_head:
        st.markdown("#### 💬 我的理解")
    with col_toggle:
        edit_mode = st.toggle("✏️ 修正", key="_v3_edit_mode",
                              help="如果我理解错了，点这里直接修改")

    if notes:
        st.markdown(f"> {notes}")

    label_map = {
        "protein_name": ("🧬", "研究对象"),
        "sample_type": ("📏", "样品尺度"),
        "goal": ("🎯", "目标"),
        "microscope": ("🔬", "设备"),
        "resolution_target": ("💎", "分辨率"),
        "experience": ("👤", "经验"),
    }

    if edit_mode:
        # ── 编辑模式：可修改的控件 ──────────────────────────
        st.caption("修改后下方路线会自动更新")
        cols = st.columns(3)
        for idx, (key, (icon, label)) in enumerate(label_map.items()):
            with cols[idx % 3]:
                if key == "protein_name":
                    new_val = st.text_input(
                        f"{icon} {label}",
                        value=profile.get(key, ""),
                        key=f"_v3_edit_{key}",
                        placeholder="如 TRPV1",
                    )
                else:
                    options = _FIELD_OPTIONS.get(key, [""])
                    cur = profile.get(key, "")
                    cur_idx = options.index(cur) if cur in options else 0
                    new_val = st.selectbox(
                        f"{icon} {label}",
                        options=options,
                        index=cur_idx,
                        key=f"_v3_edit_{key}",
                        format_func=lambda x: x or "（未指定）",
                    )
                # 回写到 profile（就是 session_state 里 _v3_extracted 的引用）
                profile[key] = new_val
    else:
        # ── 展示模式：只读卡片 ──────────────────────────────
        cols = st.columns(3)
        idx = 0
        for key, (icon, label) in label_map.items():
            val = profile.get(key, "")
            if val:
                with cols[idx % 3]:
                    st.markdown(
                        f"<div style='background:#f1f5f9;border-radius:8px;padding:8px 10px;margin-bottom:6px;'>"
                        f"<span style='font-size:0.75rem;color:#64748b;'>{icon} {label}</span><br>"
                        f"<span style='font-weight:600;color:#1e293b;'>{val}</span></div>",
                        unsafe_allow_html=True,
                    )
                idx += 1

        if idx == 0:
            st.caption("⚠️ 信息不太够，点右上角「✏️ 修正」补充，或改用快速选择问卷。")


def _render_workflow_graph(workflow: dict, app: Any) -> None:
    """用 Graphviz 渲染路线图。"""
    try:
        from utils.workflow_graph import build_workflow_dot

        theme = st.session_state.get("ui_theme", "静谧蓝")
        is_dark = theme == "深邃黑"
        accent_map = {
            "静谧蓝": "#3b82f6", "墨竹绿": "#059669",
            "雅致紫": "#7c3aed", "深邃黑": "#38bdf8",
        }
        accent = accent_map.get(theme, "#3b82f6")

        dot = build_workflow_dot(workflow, theme_accent=accent, is_dark=is_dark)
        st.graphviz_chart(dot, use_container_width=True)
        st.caption("🔵 实线框=需要做的步骤　⊝ 灰色虚线=已跳过　▶ =当前位置")
    except Exception as exc:
        # graphviz 不可用时降级为文字列表
        st.caption(f"（流程图渲染降级为列表：{exc}）")
        steps = workflow.get("steps", [])
        for s in steps:
            st.markdown(f"- {s}")
