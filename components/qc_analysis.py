"""StructPilot v6.0 — QC 回溯分析组件（P0-3）

功能：
1. 接收用户粘贴的 cryoSPARC QC 文本日志或描述
2. 支持截图上传（自动 OCR 提取关键指标）
3. 解析关键指标：分辨率、颗粒数、FSC 曲线异常特征
4. LLM 诊断 + RAG 检索课题组经验
5. 返回结构化建议（带来源标注）

调用方：main.py 聊天界面或独立 QC 分析面板。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


def render_qc_analysis_panel(
    key_prefix: str = "qc_analysis",
    llm_agent=None,
    retriever=None,
) -> Optional[Dict[str, Any]]:
    """渲染 QC 分析输入面板，返回分析结果。

    Parameters
    ----------
    key_prefix : str
        Streamlit widget key 前缀。
    llm_agent : LLMAgent, optional
        用于生成 LLM 诊断的智能体。
    retriever : KnowledgeRetriever, optional
        用于检索课题组经验的检索器。

    Returns
    -------
    Optional[Dict[str, Any]]
        若用户提交了分析请求，返回诊断结果字典：
        {
            "raw_input": str,          # 原始输入文本
            "extracted_metrics": dict, # 提取的指标
            "diagnosis": str,          # LLM 诊断
            "lab_experiences": list,   # 关联的课题组经验
        }
        若未提交或解析失败，返回 None。
    """
    st.markdown("### 🔍 QC 结果分析")
    st.caption("粘贴 cryoSPARC 运行日志或描述问题，系统将自动提取关键指标并给出诊断建议。")

    # 输入区
    input_text = st.text_area(
        "QC 日志或问题描述",
        placeholder="例如：Homogeneous Refinement 跑完，分辨率停在 4.8Å，FSC 曲线在 0.3 处断崖式下降...",
        height=150,
        key=f"{key_prefix}_text",
    )

    # 截图上传（可选）
    uploaded_image = st.file_uploader(
        "上传 QC 截图（可选）",
        type=["png", "jpg", "jpeg"],
        key=f"{key_prefix}_image",
        help="支持 FSC 曲线图、分辨率报告等截图，系统将自动 OCR 提取关键信息。",
    )

    # 提交按钮
    if st.button("🔍 开始分析", key=f"{key_prefix}_submit", type="primary"):
        if not input_text and not uploaded_image:
            st.warning("请输入 QC 日志或上传截图。")
            return None

        with st.spinner("分析中..."):
            # 1. 提取关键指标
            metrics = _extract_qc_metrics(input_text)

            # 2. 处理截图（OCR）
            if uploaded_image:
                ocr_text = _extract_text_from_image(uploaded_image)
                ocr_metrics = _extract_qc_metrics(ocr_text)
                metrics.update(ocr_metrics)

            # 3. LLM 诊断（结合 RAG）
            diagnosis, citations = _generate_diagnosis(
                input_text,
                metrics,
                llm_agent=llm_agent,
                retriever=retriever,
            )

            result = {
                "raw_input": input_text,
                "extracted_metrics": metrics,
                "diagnosis": diagnosis,
                "citations": citations,
            }

            # 渲染结果
            _render_qc_result(result)
            return result

    return None


def _extract_qc_metrics(text: str) -> Dict[str, Any]:
    """从文本中提取 QC 关键指标。

    支持提取：
    - 分辨率（resolution）：x.xÅ、x.x A
    - 颗粒数（particles）：xxx particles、xxx颗、xxx个颗粒
    - FSC 特征（fsc_*）：FSC 曲线在 0.x 处下降
    """
    metrics: Dict[str, Any] = {}
    text = text or ""

    # 分辨率
    res_match = re.search(r"(\d+\.?\d*)\s*[AÅ]", text, re.IGNORECASE)
    if res_match:
        metrics["resolution_angstrom"] = float(res_match.group(1))

    # 颗粒数
    particle_patterns = [
        r"(\d+)\s*particles",
        r"(\d+)\s*颗",
        r"(\d+)\s*个颗粒",
    ]
    for pattern in particle_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metrics["particle_count"] = int(match.group(1))
            break

    # FSC 特征
    fsc_match = re.search(r"FSC.*?([01]\.?\d*)", text, re.IGNORECASE)
    if fsc_match:
        metrics["fsc_threshold"] = float(fsc_match.group(1))

    return metrics


def _extract_text_from_image(uploaded_file) -> str:
    """从上传的图像中提取文本（OCR）。

    注意：此函数需集成项目现有的 OCR 逻辑（utils.image_processing.run_local_ocr）。
    """
    try:
        # 延迟导入，避免循环依赖
        from utils.image_processing import run_local_ocr
        from PIL import Image
        import io

        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        ocr_result = run_local_ocr(image)
        return ocr_result or ""
    except Exception:
        return ""


def _generate_diagnosis(
    input_text: str,
    metrics: Dict[str, Any],
    llm_agent=None,
    retriever=None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """生成 LLM 诊断 + RAG 引用。

    Returns
    -------
    Tuple[str, List[Dict[str, Any]]]
        (诊断文本, citations列表)
    """
    # 构建诊断 Prompt
    prompt_parts = [
        "你是 cryoSPARC 专家，请根据以下 QC 结果诊断问题并给出建议：\n",
        f"**用户描述**：{input_text}\n",
    ]

    if metrics:
        prompt_parts.append("**提取的关键指标**：")
        for key, value in metrics.items():
            prompt_parts.append(f"  - {key}: {value}")
        prompt_parts.append("")

    # RAG 检索课题组经验
    citations = []
    if retriever:
        query = input_text or "QC 问题诊断"
        try:
            retrieved = retriever.search(query, top_k=5, min_score=0.4)
            if retrieved:
                prompt_parts.append("**参考经验**：")
                for i, (doc_id, text, score) in enumerate(retrieved, start=1):
                    snippet = text[:200] if len(text) > 200 else text
                    prompt_parts.append(f"  [{i}] {snippet} (来源: {doc_id}, 置信度: {score:.2f})")
                    citations.append({
                        "ref": f"R{i}",
                        "doc_id": doc_id,
                        "score": score,
                        "source_type": "lab_exp" if str(doc_id).startswith("lab_") else "discussion",
                        "snippet": snippet,
                    })
        except Exception:
            pass

    prompt_parts.append("\n请给出：\n1. 问题判断\n2. 可能原因\n3. 解决建议\n4. 参数调整方向")

    prompt = "\n".join(prompt_parts)

    # 调用 LLM
    diagnosis = ""
    if llm_agent:
        try:
            diagnosis = llm_agent.chat(prompt, max_tokens=800)
        except Exception as e:
            diagnosis = f"（LLM 诊断暂时不可用：{e}）"

    if not diagnosis:
        diagnosis = "暂无诊断结果，请检查 LLM 配置。"

    return diagnosis, citations


def _render_qc_result(result: Dict[str, Any]) -> None:
    """渲染 QC 分析结果。"""
    st.markdown("---")
    st.markdown("### 📊 分析结果")

    # 提取的指标
    metrics = result.get("extracted_metrics", {})
    if metrics:
        st.markdown("**关键指标**")
        cols = st.columns(len(metrics))
        for i, (key, value) in enumerate(metrics.items()):
            with cols[i]:
                st.metric(label=key.replace("_", " ").title(), value=value)

    # LLM 诊断
    diagnosis = result.get("diagnosis", "")
    if diagnosis:
        st.markdown("**诊断建议**")
        st.markdown(diagnosis)

    # 引用来源（复用 answer_source_display 逻辑）
    citations = result.get("citations", [])
    if citations:
        st.markdown("**参考依据**")
        from components.answer_source_display import render_answer_sources
        # 构造临时 qa_trace 格式
        fake_trace = {"citations": citations}
        render_answer_sources(fake_trace, key_prefix="qc_src")

        fake_trace = {"citations": citations}
        render_answer_sources(fake_trace, key_prefix="qc_result")
