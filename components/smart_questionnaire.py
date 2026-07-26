"""智能对话式问卷 - AI动态提问，自然语言理解

架构设计：
1. 用户选择模式：快速模式（固定问卷）或 智能模式（AI对话）
2. 智能模式：AI根据上一个回答，动态生成下一个问题
3. 最后提取结构化信息并让用户确认

使用方式：
    from components.smart_questionnaire import render_smart_questionnaire

    user_profile = render_smart_questionnaire()
    if user_profile:
        # 用户完成问卷，获得结构化画像
        st.write(user_profile)
"""

from __future__ import annotations
import streamlit as st
from typing import Dict, Any, Optional, List
import json


# 问题库（AI会根据上下文选择合适的问题）
QUESTION_TEMPLATES = {
    "sample_type": {
        "question": "您好！请告诉我您的样品类型是什么？",
        "hints": ["例如：TRPV1膜蛋白、核糖体、病毒衣壳等"],
        "extract_key": "sample_type"
    },
    "target_resolution": {
        "question": "您希望达到什么样的分辨率？",
        "hints": ["例如：3Å高分辨、5-10Å中等分辨、或者只是初步质检"],
        "extract_key": "target_resolution"
    },
    "microscope": {
        "question": "您使用的是什么型号的电镜？",
        "hints": ["例如：Titan Krios 300kV、Talos Arctica 200kV"],
        "extract_key": "microscope"
    },
    "particle_size": {
        "question": "您的颗粒大小大约是多少？",
        "hints": ["例如：150kDa（中等）、<100kDa（小型）、>500kDa（大型）"],
        "extract_key": "particle_size"
    },
    "experience": {
        "question": "您之前有冷冻电镜数据处理的经验吗？",
        "hints": ["例如：第一次使用、用过几次、比较熟悉"],
        "extract_key": "experience"
    }
}


def _extract_info_from_answer(question_key: str, answer: str, app: Any) -> Dict[str, Any]:
    """使用LLM从用户回答中提取结构化信息

    Parameters
    ----------
    question_key : str
        问题的key（sample_type, target_resolution等）
    answer : str
        用户的回答
    app : StructPilotApp
        应用实例（用于调用LLM）

    Returns
    -------
    dict
        提取的结构化信息，如 {"sample_type": "膜蛋白", "protein_name": "TRPV1"}
    """
    # 构造提取prompt
    extract_prompt = f"""从用户的回答中提取冷冻电镜实验的相关信息。

问题：{QUESTION_TEMPLATES[question_key]['question']}
用户回答：{answer}

请提取以下信息（如果用户提到了的话）：
- sample_type: 样品类型（膜蛋白、核糖体、病毒等）
- protein_name: 蛋白质名称（如果提到了具体名称）
- target_resolution: 目标分辨率（高分辨<4Å、中等5-10Å、低分辨>10Å）
- microscope: 设备型号（Titan Krios 300kV、Talos Arctica 200kV等）
- particle_size: 颗粒大小（small <150kDa、medium 150-500kDa、large >500kDa）
- experience: 经验水平（新手、有经验、熟练）

以JSON格式返回，只返回提到的字段。例如：
{{"sample_type": "膜蛋白", "protein_name": "TRPV1", "target_resolution": "高分辨"}}

JSON:"""

    try:
        # 调用LLM提取信息
        from graph.state import PipelineState
        state = PipelineState()
        state.user_input = extract_prompt
        state.software = "cryosparc"  # 默认

        # 使用简单的文本生成节点
        result = app.graph.invoke(state)

        # 解析LLM返回的JSON
        answer_text = result.last_answer or ""

        # 尝试从markdown代码块中提取JSON
        if "```json" in answer_text:
            json_str = answer_text.split("```json")[1].split("```")[0].strip()
        elif "```" in answer_text:
            json_str = answer_text.split("```")[1].split("```")[0].strip()
        else:
            # 直接尝试解析
            json_str = answer_text.strip()

        extracted = json.loads(json_str)
        return extracted
    except Exception as e:
        # LLM失败，使用规则兜底
        return _rule_extract_info(question_key, answer)


def _rule_extract_info(question_key: str, answer: str) -> Dict[str, Any]:
    """规则兜底：从回答中提取信息（当LLM不可用时）"""
    low = answer.lower()
    result = {}

    if question_key == "sample_type":
        if any(k in low for k in ["膜蛋白", "gpcr", "trpv", "离子通道", "受体"]):
            result["sample_type"] = "中等蛋白复合物"
        elif any(k in low for k in ["核糖体", "ribosome", "剪接体", "大型"]):
            result["sample_type"] = "大型复合物"
        elif any(k in low for k in ["病毒", "virus", "衣壳", "capsid"]):
            result["sample_type"] = "病毒/高对称颗粒"
        elif any(k in low for k in ["小蛋白", "小型", "单体"]):
            result["sample_type"] = "小型蛋白/复合物"

    elif question_key == "target_resolution":
        if any(k in low for k in ["高分辨", "原子", "3", "4", "近原子"]):
            result["target_resolution"] = "高分辨"
        elif any(k in low for k in ["中等", "5", "6", "7", "8", "9", "10"]):
            result["target_resolution"] = "中等"
        elif any(k in low for k in ["粗", "初步", "快速", "质检"]):
            result["target_resolution"] = "粗筛"

    elif question_key == "microscope":
        if any(k in low for k in ["krios", "300", "titan"]):
            result["microscope"] = "Krios 300kV"
        elif any(k in low for k in ["arctica", "talos", "200", "glacios"]):
            result["microscope"] = "Arctica 200kV"

    elif question_key == "particle_size":
        if any(k in low for k in ["小", "小型", "<100", "<150", "50k", "80k", "100k"]):
            result["particle_size"] = "small"
        elif any(k in low for k in ["大", "大型", ">500", "megadalton", "mda"]):
            result["particle_size"] = "large"
        else:
            result["particle_size"] = "medium"

    elif question_key == "experience":
        if any(k in low for k in ["新手", "第一次", "没用过", "不懂", "小白"]):
            result["experience"] = "新手"
        elif any(k in low for k in ["熟", "很多次", "经常", "专业"]):
            result["experience"] = "熟练"
        else:
            result["experience"] = "有经验"

    return result


def _generate_next_question(current_profile: Dict[str, Any], answer_history: List[str]) -> Optional[str]:
    """根据当前已收集的信息，决定下一个问题

    Parameters
    ----------
    current_profile : dict
        当前已提取的用户画像
    answer_history : list
        已回答的问题key列表

    Returns
    -------
    str or None
        下一个问题的key，None表示问卷结束
    """
    # 问题优先级顺序
    question_order = ["sample_type", "target_resolution", "microscope", "particle_size", "experience"]

    for q_key in question_order:
        if q_key not in answer_history:
            return q_key

    return None  # 所有问题都已回答


def render_smart_questionnaire(app: Any) -> Optional[Dict[str, Any]]:
    """渲染智能对话式问卷

    Parameters
    ----------
    app : StructPilotApp
        应用实例（用于调用LLM）

    Returns
    -------
    dict or None
        完成后返回用户画像，未完成返回None
    """
    # 初始化session state
    if "sq_mode" not in st.session_state:
        st.session_state["sq_mode"] = None  # None表示未选择，"fast"或"smart"

    if "sq_current_question" not in st.session_state:
        st.session_state["sq_current_question"] = None

    if "sq_answers" not in st.session_state:
        st.session_state["sq_answers"] = {}  # {question_key: answer_text}

    if "sq_profile" not in st.session_state:
        st.session_state["sq_profile"] = {}  # 提取的结构化信息

    if "sq_history" not in st.session_state:
        st.session_state["sq_history"] = []  # 已回答的问题key列表

    # 模式选择由 modes/beginner.py 统一负责，这里直接进入智能问卷
    if st.session_state["sq_mode"] is None:
        st.session_state["sq_mode"] = "smart"
    if st.session_state["sq_current_question"] is None and not st.session_state["sq_history"]:
        st.session_state["sq_current_question"] = "sample_type"

    # 智能模式 - 多轮对话
    if st.session_state["sq_mode"] == "smart":
        st.markdown("### 🤖 智能问卷")

        # 显示进度
        total_questions = len(QUESTION_TEMPLATES)
        answered = len(st.session_state["sq_history"])
        st.progress(answered / total_questions, text=f"进度：{answered}/{total_questions}")

        # 显示对话历史
        if st.session_state["sq_history"]:
            with st.expander("📝 已回答的问题", expanded=False):
                for q_key in st.session_state["sq_history"]:
                    st.markdown(f"**Q:** {QUESTION_TEMPLATES[q_key]['question']}")
                    st.markdown(f"**A:** {st.session_state['sq_answers'][q_key]}")
                    st.divider()

        # 当前问题
        current_q_key = st.session_state["sq_current_question"]

        if current_q_key is None:
            # 所有问题已回答，显示确认页面
            st.success("✅ 问卷完成！")

            st.markdown("### 📋 我们理解的您的需求：")
            profile = st.session_state["sq_profile"]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("样品类型", profile.get("sample_type", "未指定"))
                st.metric("目标分辨率", profile.get("target_resolution", "未指定"))
            with col2:
                st.metric("设备型号", profile.get("microscope", "未指定"))
                st.metric("经验水平", profile.get("experience", "未指定"))

            col_confirm, col_restart = st.columns(2)
            with col_confirm:
                if st.button("✅ 确认无误", use_container_width=True, type="primary"):
                    result = st.session_state["sq_profile"].copy()
                    # 清空状态
                    st.session_state["sq_mode"] = None
                    st.session_state["sq_current_question"] = None
                    st.session_state["sq_answers"] = {}
                    st.session_state["sq_profile"] = {}
                    st.session_state["sq_history"] = []
                    return result

            with col_restart:
                if st.button("🔄 重新填写", use_container_width=True):
                    st.session_state["sq_current_question"] = "sample_type"
                    st.session_state["sq_answers"] = {}
                    st.session_state["sq_profile"] = {}
                    st.session_state["sq_history"] = []
                    st.rerun()

            return None

        # 显示当前问题
        question_config = QUESTION_TEMPLATES[current_q_key]
        st.markdown(f"### {question_config['question']}")

        for hint in question_config['hints']:
            st.caption(f"💡 {hint}")

        # 输入回答
        user_answer = st.text_area(
            "请输入您的回答",
            placeholder="用自然语言描述即可，AI会理解您的意思...",
            height=100,
            key=f"answer_{current_q_key}"
        )

        col_next, col_skip = st.columns([3, 1])
        with col_next:
            if st.button("下一步 →", use_container_width=True, type="primary", disabled=not user_answer.strip()):
                if user_answer.strip():
                    # 保存回答
                    st.session_state["sq_answers"][current_q_key] = user_answer
                    st.session_state["sq_history"].append(current_q_key)

                    # 提取结构化信息
                    with st.spinner("AI正在理解您的回答..."):
                        extracted = _extract_info_from_answer(current_q_key, user_answer, app)
                        st.session_state["sq_profile"].update(extracted)

                    # 生成下一个问题
                    next_q = _generate_next_question(
                        st.session_state["sq_profile"],
                        st.session_state["sq_history"]
                    )
                    st.session_state["sq_current_question"] = next_q
                    st.rerun()

        with col_skip:
            if st.button("跳过", use_container_width=True):
                st.session_state["sq_history"].append(current_q_key)
                next_q = _generate_next_question(
                    st.session_state["sq_profile"],
                    st.session_state["sq_history"]
                )
                st.session_state["sq_current_question"] = next_q
                st.rerun()

        return None

    return None
