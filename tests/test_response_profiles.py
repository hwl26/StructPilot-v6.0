from __future__ import annotations

import tempfile

from agents.memory_agent import MemoryAgent
from agents.llm_agent import LLMAgent
from agents.expert_agent import ExpertAgent
from agents.smart_qa_engine import (
    AnswerComposerAgent,
    QueryUnderstanding,
    RetrievalResult,
    SOPReasoning,
)
from response_profiles import (
    detect_response_focus,
    format_response_for_profile,
    has_required_structure,
    required_headings,
    response_focus_instruction,
)
from graph.app import StructPilotApp
from graph.state import PipelineState


SOURCE_ANSWER = (
    "当前判断：box size 应覆盖颗粒并保留足够边缘。"
    "下一步先测量颗粒直径，再按像素尺寸换算。"
    "参数 box size 建议至少覆盖完整颗粒。"
    "注意 box 过小会裁切信号。"
    "QC 检查颗粒是否完整居中。"
    "替代方案是先用较大 box 提取。"
    "若失败则回退并重新提取。"
    "参考来源：官方流程规则。"
)


def test_profiles_keep_same_conclusion_and_have_distinct_depths():
    answers = {
        profile: format_response_for_profile(SOURCE_ANSWER, profile)
        for profile in ("concise", "teaching", "expert")
    }

    conclusion = "当前判断：box size 应覆盖颗粒并保留足够边缘。"
    assert all(conclusion in answer for answer in answers.values())
    assert len(answers["concise"]) < len(answers["teaching"]) < len(answers["expert"])
    assert all(has_required_structure(answer, profile) for profile, answer in answers.items())


def test_concise_keeps_risk_and_evidence_instead_of_hiding_them():
    answer = format_response_for_profile(SOURCE_ANSWER, "concise")
    assert "**关键风险**" in answer
    assert "box 过小会裁切信号" in answer
    assert "**证据来源**" in answer
    assert "官方流程规则" in answer


def test_teaching_and_expert_expose_expected_scientific_sections():
    teaching = format_response_for_profile(SOURCE_ANSWER, "teaching")
    expert = format_response_for_profile(SOURCE_ANSWER, "expert")

    assert "**参数解释**" in teaching
    assert "**常见错误**" in teaching
    assert "**QC标准**" in expert
    assert "QC 检查颗粒是否完整居中" in expert
    assert "**回退路径**" in expert
    assert "重新提取" in expert
    assert "**不确定性**" in expert


def test_answer_composer_records_profile_and_changes_output_shape():
    composer = AnswerComposerAgent()
    understanding = QueryUnderstanding(
        detected_stage="cp_05",
        detected_stage_name="颗粒提取",
        detected_software="relion",
        user_intent="parameter_advice",
        confidence=0.9,
    )
    reasoning = SOPReasoning(
        stage_judgment="box size 需要覆盖完整颗粒。",
        problem_analysis="box 过小会裁切信号。",
        knowledge_basis=["RELION 官方流程"],
        recommended_params=[{"param": "box size", "value": "按粒径换算", "reason": "保留边缘"}],
        operation_steps=["测量粒径", "按像素尺寸换算", "检查提取结果"],
        qc_judgment="QC 检查颗粒完整且居中",
        risk_warnings=["不要直接套用其他数据集的 box size"],
        next_step_hint="先在少量颗粒上试提取。",
    )
    retrieval = RetrievalResult(source="hybrid")

    concise = composer.compose(understanding, reasoning, retrieval, "relion", "concise")
    expert = composer.compose(understanding, reasoning, retrieval, "relion", "expert")

    assert concise.structured_json["response_profile"] == "concise"
    assert expert.structured_json["response_profile"] == "expert"
    assert required_headings("concise")[0] in concise.formatted_markdown
    assert "QC标准" in expert.formatted_markdown
    assert len(concise.formatted_markdown) < len(expert.formatted_markdown)


def test_llm_prompts_receive_the_selected_profile():
    llm = LLMAgent()
    prompt = llm._rewrite_prompt("box size 怎么设", "按粒径换算", response_profile="expert")
    system = llm._system_prompt("concise")

    assert "回答焦点=参数建议" in prompt
    assert "回答深度=专家" in prompt
    assert "QC标准" in prompt
    assert "回答深度=简洁" in system
    assert "证据来源" in system


def test_response_focus_is_inferred_from_user_question():
    assert detect_response_focus("box size 怎么设") == "parameter"
    assert detect_response_focus("上传 CTF 截图问是否合格") == "multimodal"
    assert detect_response_focus("2D class 该不该保留") == "qc"
    assert detect_response_focus("报错 failed 怎么办") == "troubleshooting"
    assert detect_response_focus("分辨率不够时应该怎么建模？Cα trace 够吗？") == "decision"
    assert "不给伪精确数值" in response_focus_instruction("能提多少分辨率？")


def test_low_resolution_model_building_does_not_answer_handedness():
    state = PipelineState(session_id="low_res_modeling")
    state.software = "relion"
    state.current_cp_id = "cp_12"
    state.current_cp_name = "模型构建与验证"

    answer = ExpertAgent().explain(state, "分辨率不够时应该怎么建模？Cα trace 够吗？")

    assert "Cα trace" in answer
    assert "完整原子模型" in answer
    assert "handedness 检查" not in answer


def test_app_handle_updates_dict_result_and_keeps_answer_on_topic():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = LLMAgent()
        llm.enabled = False
        app = StructPilotApp(memory=MemoryAgent(tmpdir), llm=llm)
        state = PipelineState(session_id="low_res_handle")
        state.software = "relion"
        state.current_cp_id = "cp_12"
        state.current_cp_name = "模型构建与验证"

        result = app.handle(state, "分辨率不够时应该怎么建模？Cα trace 够吗？", response_profile="teaching")

    assert result.action_tag == "param_advice"
    assert "Cα trace" in result.agent_reply
    assert "handedness 检查在 RELION 官方 tutorial" not in result.agent_reply
    assert result.last_qa_trace["response_focus"] == "decision"


def test_app_handle_persists_generation_profile_in_message_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = LLMAgent()
        llm.enabled = False
        app = StructPilotApp(memory=MemoryAgent(tmpdir), llm=llm)
        state = PipelineState(session_id="profile_metadata_test")

        result = app.handle(state, "进度", response_profile="expert")

    assistant = next(msg for msg in reversed(result.messages) if msg.role == "assistant")
    user = next(msg for msg in reversed(result.messages) if msg.role == "user")
    assert result.response_profile == "expert"
    assert assistant.metadata["response_profile"] == "expert"
    assert assistant.metadata["qa_trace"]["response_profile"] == "expert"
    assert assistant.metadata["qa_trace"]["response_focus"] == "progress"
    assert user.metadata["response_profile"] == "expert"
    assert "**QC标准**" in assistant.content


def test_memory_round_trip_keeps_multimodal_evidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemoryAgent(tmpdir)
        state = PipelineState(session_id="image_round_trip")
        state.add_message(
            "user",
            "请判断这张图",
            metadata={
                "response_profile": "concise",
                "image_observations": [{"stage_guess": "cp_03", "confidence": 0.88}],
            },
            image_refs=[{
                "image_name": "ctf.png",
                "image_path": "runtime/uploads/ctf.png",
                "mime_type": "image/png",
                "sha256": "abc123",
                "width": 800,
                "height": 600,
                "source_type": "upload",
            }],
        )
        memory.save_state(state)
        restored = memory.load_state(state.session_id)

    assert restored is not None
    assert restored.messages[0].image_refs[0]["image_name"] == "ctf.png"
    assert restored.messages[0].metadata["image_observations"][0]["stage_guess"] == "cp_03"
