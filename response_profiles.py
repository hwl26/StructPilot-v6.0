"""Response depth profiles shared by orchestration, prompts, and UI.

The formatter is deliberately deterministic. LLM prompts should normally
produce the requested structure, while this module guarantees that rule-only
and degraded paths still expose the same scientific sections.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Literal


ResponseProfile = Literal["concise", "teaching", "expert"]
ResponseFocus = Literal[
    "parameter",
    "qc",
    "troubleshooting",
    "operation",
    "decision",
    "concept",
    "multimodal",
    "progress",
    "general",
]

DEFAULT_RESPONSE_PROFILE: ResponseProfile = "teaching"
PROFILE_LABELS: Dict[str, str] = {
    "concise": "快速模式",
    "teaching": "教学模式",
    "expert": "专家模式",
}
PROFILE_DESCRIPTIONS: Dict[str, str] = {
    "concise": "简洁直接的回答：给出结论、下一步、关键风险和证据来源",
    "teaching": "循序渐进的引导：附带解释、原因、操作步骤、参数解释和常见错误",
    "expert": "深入详尽的分析：给出假设、参数边界、QC标准、替代方案、回退路径和证据等级",
}
FOCUS_LABELS: Dict[str, str] = {
    "parameter": "参数建议",
    "qc": "质控判断",
    "troubleshooting": "故障排查",
    "operation": "操作指导",
    "decision": "决策建议",
    "concept": "概念解释",
    "multimodal": "图像/语音证据判断",
    "progress": "流程状态",
    "general": "通用问答",
}


def normalize_response_profile(value: str | None) -> ResponseProfile:
    value = str(value or "").strip().lower()
    if value in PROFILE_LABELS:
        return value  # type: ignore[return-value]
    return DEFAULT_RESPONSE_PROFILE


def detect_response_focus(
    user_text: str | None,
    action_tag: str | None = "",
    context: str | None = "",
) -> ResponseFocus:
    """Infer what the answer should spend most of its detail on.

    This is intentionally deterministic and lightweight. It does not decide
    domain truth; it only helps the LLM and deterministic formatter avoid
    answering every question with the same generic template emphasis.
    """
    action = (action_tag or "").strip().lower()
    text = f"{user_text or ''}\n{context or ''}".lower()

    if action in {"fault_diagnosis"}:
        return "troubleshooting"
    if action in {"stage_guide", "stage_guide_sop"}:
        return "operation"
    if action in {"plot_interpretation"}:
        return "qc"
    if action in {"concept_explain"}:
        return "concept"
    if action in {"progress", "report"}:
        return "progress"

    if any(k in text for k in ("截图", "图片", "图像", "上传", "ocr", "视觉", "语音", "audio", "voice", "ctf图")):
        return "multimodal"
    if any(k in text for k in ("报错", "错误", "失败", "异常", "不好", "很差", "差", "条纹", "模糊", "漂移", "偏侧", "不收敛")):
        return "troubleshooting"
    if any(k in text for k in ("合格", "是否通过", "能不能过", "该不该保留", "要不要保留", "质控", "qc", "fsc", "class", "分辨率达标")):
        return "qc"
    if any(k in text for k in ("够吗", "够不够", "能不能", "可不可以", "该不该", "要不要", "做不做")):
        return "decision"
    if any(k in text for k in ("建模", "模型构建", "原子模型", "cα", "ca trace", "trace", "modelangelo", "coot", "phenix")):
        return "decision"
    if any(k in text for k in ("参数", "怎么设", "如何设置", "设多少", "多少合适", "推荐值", "box", "pixel", "dose", "阈值", "resolution", "分辨率", "bfactor")):
        return "parameter"
    if action in {"param_advice"}:
        return "parameter"
    if any(k in text for k in ("还是", "哪个好", "选择", "选哪", "对比", "区别", "要不要", "做不做", "该不该")):
        return "decision"
    if any(k in text for k in ("是什么", "什么是", "什么意思", "解释", "定义", "原理", "为什么", "影响")):
        return "concept"
    if any(k in text for k in ("怎么做", "如何做", "步骤", "流程", "sop", "教程", "下一步", "开始", "继续")):
        return "operation"
    if any(k in text for k in ("进度", "报告", "完成", "跳过", "状态")):
        return "progress"
    return "general"


def response_focus_instruction(
    user_text: str | None,
    action_tag: str | None = "",
    context: str | None = "",
) -> str:
    focus = detect_response_focus(user_text, action_tag, context)
    instructions = {
        "parameter": (
            "回答焦点=参数建议。优先回答具体参数如何设、为什么这样设、适用边界和需要补充的输入；"
            "没有粒径、pixel size、目标分辨率等证据时，给计算方法和需补充项，不给伪精确数值。"
        ),
        "qc": (
            "回答焦点=质控判断。优先说明是否能通过/保留、判断依据、最低需要看的图或指标、"
            "关键风险和下一步验证。不能仅给泛泛操作步骤。"
        ),
        "troubleshooting": (
            "回答焦点=故障排查。优先列最可能原因、按优先级检查、可逆修复动作和失败后的回退路径；"
            "不要把症状未支持的故障说成确定结论。"
        ),
        "operation": (
            "回答焦点=操作指导。优先给当前步骤、菜单/任务顺序、输入输出和完成判据；"
            "参数解释只保留与当前操作直接相关的内容。"
        ),
        "decision": (
            "回答焦点=决策建议。优先给推荐选项、选择条件、对比取舍、风险和保守回退方案；"
            "如果缺少关键证据，先列需要补充的决策依据。"
        ),
        "concept": (
            "回答焦点=概念解释。优先解释定义、在 cryo-EM 流程中的作用、与软件任务的对应关系，"
            "只在确有依据时给参数或阈值。"
        ),
        "multimodal": (
            "回答焦点=图像/语音证据判断。优先复述系统实际识别到的图像/OCR/语音摘要、可见证据、"
            "置信度和不能从图中确认的内容，再给建议。"
        ),
        "progress": (
            "回答焦点=流程状态。优先说明当前步骤、已完成/失败/跳过项、下一步和阻塞风险；"
            "不要展开无关理论。"
        ),
        "general": (
            "回答焦点=通用问答。直接回应用户问题；若与 cryo-EM 无关，保持简短并自然引回可提供的流程支持。"
        ),
    }
    return instructions[focus]


def response_profile_instruction(profile: str | None) -> str:
    mode = normalize_response_profile(profile)
    common = (
        "所有结论必须服从规则层与可追溯证据；没有依据时明确写不确定，"
        "不得为了填满结构而编造阈值、参数或观察结果。"
    )
    instructions = {
        "concise": (
            "回答深度=简洁。严格使用四个小节：结论、下一步、关键风险、证据来源。"
            "每节只保留最关键内容，总体尽量控制在 220~500 个中文字符。"
        ),
        "teaching": (
            "回答深度=教学。使用六个小节：结论、原因、操作步骤、参数解释、"
            "常见错误、证据来源。说明为什么这样做，适合正在学习流程的用户。"
        ),
        "expert": (
            "回答深度=专家。使用九个小节：结论、前提假设、专业分析、参数边界、"
            "QC标准、替代方案、回退路径、证据等级、不确定性。明确适用条件、"
            "决策边界和失败后的可逆操作。"
        ),
    }
    return instructions[mode] + common


def required_headings(profile: str | None) -> List[str]:
    mode = normalize_response_profile(profile)
    return {
        "concise": ["结论", "下一步", "关键风险", "证据来源"],
        "teaching": ["结论", "原因", "操作步骤", "参数解释", "常见错误", "证据来源"],
        "expert": [
            "结论", "前提假设", "专业分析", "参数边界", "QC标准",
            "替代方案", "回退路径", "证据等级", "不确定性",
        ],
    }[mode]


def has_required_structure(text: str, profile: str | None) -> bool:
    return all(
        re.search(
            rf"(?:^|\n)\s*(?:#{{1,6}}\s*)?\*{{0,2}}{re.escape(title)}\*{{0,2}}",
            text or "",
            re.I,
        )
        for title in required_headings(profile)
    )


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line or "").strip()
    line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", "", line).strip()
    line = line.strip("*_` ")
    return line


def _content_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").splitlines():
        for part in re.split(r"(?<=[。！？；])\s*", raw):
            clean = _clean_line(part)
            if not clean or clean in {"---", "补充要点"}:
                continue
            if clean in {
                "结论", "当前判断", "下一步", "关键风险", "证据来源", "原因",
                "操作步骤", "操作方案", "参数解释", "参数建议", "常见错误",
                "前提假设", "专业分析", "参数边界", "QC标准", "质控判断",
                "替代方案", "回退路径", "证据等级", "不确定性", "可能问题",
                "建议检查", "决策选项", "需补充信息", "参考来源",
            }:
                continue
            if clean not in lines:
                lines.append(clean)
    return lines


def _core_answer_text(text: str) -> str:
    """Remove appended audit/diagnostic ledgers before section extraction."""
    cleaned = text or ""
    cut_markers = (
        "\n\n---\n\n**证据与不确定性",
        "\n\n---\n\n**Evidence",
        "\n\n证据与不确定性",
        "\n\n参考来源：",
    )
    for marker in cut_markers:
        idx = cleaned.find(marker)
        if idx >= 0:
            cleaned = cleaned[:idx]
    return cleaned.strip()


def _matching(lines: Iterable[str], keywords: Iterable[str], limit: int = 4) -> List[str]:
    keys = tuple(k.lower() for k in keywords)
    result = [line for line in lines if any(k in line.lower() for k in keys)]
    return result[:limit]


def _first(lines: List[str], fallback: str) -> str:
    return lines[0] if lines else fallback


def _bullets(items: List[str], fallback: str) -> str:
    values = items or [fallback]
    return "\n".join(f"- {item}" for item in values)


def _numbered(items: List[str], fallback: str) -> str:
    values = items or [fallback]
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(values, 1))


def format_response_for_profile(
    text: str,
    profile: str | None,
    *,
    evidence_hint: str = "",
    uncertainty_hint: str = "",
) -> str:
    """Return a stable profile-specific answer without inventing domain facts."""
    mode = normalize_response_profile(profile)
    original = (text or "").strip()
    if not original:
        original = "当前没有足够信息形成可靠结论。"
    if has_required_structure(original, mode):
        return original

    core_original = _core_answer_text(original)
    lines = _content_lines(core_original)
    non_meta = [
        line for line in lines
        if not any(key in line.lower() for key in ("参考来源", "证据与不确定性", "evidence grade", "sources:"))
    ]
    conclusion = _first(non_meta, "当前信息不足，暂不能形成可靠结论。")
    steps = _matching(lines, ["下一步", "建议", "操作", "运行", "检查", "确认", "重新", "进入"], 5)
    params = _matching(lines, ["参数", "pixel", "box", "阈值", "尺寸", "分辨率", "class", "dose", "ctf"], 5)
    risks = _matching(lines, ["风险", "注意", "错误", "失败", "不确定", "避免", "警告", "不要"], 4)
    qc = _matching(lines, ["qc", "质控", "合格", "通过", "fsc", "阈值", "验证", "检查"], 5)
    alternatives = _matching(lines, ["替代", "可选", "或者", "也可以", "另一", "option"], 4)
    rollback = _matching(lines, ["回退", "重跑", "重新", "恢复", "撤销", "rollback"], 4)
    assumptions = _matching(lines, ["假设", "前提", "如果", "需提供", "需确认", "取决于"], 4)
    evidence = _matching(lines, ["参考来源", "证据", "source", "[r", "官方"], 5)
    evidence_text = _bullets(evidence, evidence_hint or "规则层结论与当前会话中可追溯的信息。")
    uncertainty = uncertainty_hint or _first(
        _matching(lines, ["不确定", "暂无", "缺少", "无法确认", "需补充"], 3),
        "未提供的数据、截图细节或实验条件仍需用户确认。",
    )

    if mode == "concise":
        return (
            f"**结论**\n\n{conclusion}\n\n"
            f"**下一步**\n\n{_first(steps, '先核对当前步骤的关键输入和质控结果，再执行下一项操作。')}\n\n"
            f"**关键风险**\n\n{_first(risks, '不要把缺少证据的参数或图像判断当作确定结论。')}\n\n"
            f"**证据来源**\n\n{evidence_text}"
        )

    analysis = core_original[:1600]
    if mode == "teaching":
        return (
            f"**结论**\n\n{conclusion}\n\n"
            f"**原因**\n\n{analysis}\n\n"
            f"**操作步骤**\n\n{_numbered(steps, '核对输入、参数和当前质控结果后再继续流程。')}\n\n"
            f"**参数解释**\n\n{_bullets(params, '当前证据不足以给出硬性参数值；参数应结合样品、像素尺寸和目标分辨率确认。')}\n\n"
            f"**常见错误**\n\n{_bullets(risks, '在证据不足时直接套用固定参数，或忽略截图与日志中的异常信号。')}\n\n"
            f"**证据来源**\n\n{evidence_text}"
        )

    return (
        f"**结论**\n\n{conclusion}\n\n"
        f"**前提假设**\n\n{_bullets(assumptions, '当前判断仅适用于用户已提供的步骤、软件和实验上下文。')}\n\n"
        f"**专业分析**\n\n{analysis}\n\n"
        f"**参数边界**\n\n{_bullets(params, '未检索到可直接迁移的硬性边界；关键参数需由数据与官方规则共同约束。')}\n\n"
        f"**QC标准**\n\n{_bullets(qc, '当前材料未提供足够的定量 QC 指标，需补充对应结果图或日志。')}\n\n"
        f"**替代方案**\n\n{_bullets(alternatives, '若主方案证据不足，保留当前结果并用独立方法交叉验证。')}\n\n"
        f"**回退路径**\n\n{_numbered(rollback, '保留原始输入与参数记录，从最近一个已通过 QC 的节点重新运行。')}\n\n"
        f"**证据等级**\n\n{evidence_text}\n\n"
        f"**不确定性**\n\n{uncertainty}"
    )
