"""Smart QA Engine — 智能问答调度层.

在现有 navigator → expert/sop/fault/plot_interp → memory 管线之上，新增一个
"理解 → 扩展 → 检索 → 推理 → 整合"的五段式智能问答管线。

管线流程：
    用户自然语言输入
      → understand_query()   (阶段识别 + 意图分类 + 缺失信息判断)
      → expand_query()       (查询扩展：中英文关键词 + stage_id + parameter_id)
      → retrieve_knowledge() (混合检索：keyword + vector + metadata filter)
      → reason_with_sop()    (SOP 推理：结合检索结果 + 用户上下文)
      → compose_answer()     (回答整合：卡片式结构化输出)

降级策略：
    无 API Key 时，understand_query 降级为规则匹配，expand_query 降级为关键词
    同义词扩展，reason_with_sop 降级为直接引用知识库，compose_answer 降级为
    固定模板拼接。整个管线始终可用，不会因缺少 LLM 而报错。

集成方式：
    在 graph/app.py 的 _polish_reply() 之前调用 SmartQAEngine.process()，
    将其产出作为增强上下文注入到现有 RAG + LLM 改写流程中。

铁律：不破坏 14 步工作流、双软件切换、固定 SOP/参数/截图展示、报告/日志功能。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from response_profiles import (
    detect_response_focus,
    format_response_for_profile,
    normalize_response_profile,
)

if TYPE_CHECKING:
    from graph.state import PipelineState
    from agents.llm_agent import LLMAgent

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB_DIR = os.path.join(_BASE_DIR, "knowledge_base")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class QueryUnderstanding:
    """understand_query() 的输出结构."""
    detected_stage: str = ""          # cp_01 ~ cp_12
    detected_stage_name: str = ""     # 中文名
    detected_software: str = ""       # cryosparc / relion / ""
    user_intent: str = ""             # parameter_advice / fault_troubleshoot / operation_guide / concept_explain / decision_advice
    problem_type: str = ""            # quality_degradation / parameter_error / data_limitation / classification_issue / ""
    mentioned_parameters: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    needs_sop: bool = False
    needs_parameter_advice: bool = False
    needs_qc_judgement: bool = False
    needs_image_match: bool = False
    needs_fault_diagnosis: bool = False
    confidence: float = 0.0           # 0.0 ~ 1.0
    should_ask_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    source: str = "rule"              # "llm" or "rule"


@dataclass
class QueryExpansion:
    """expand_query() 的输出结构."""
    search_queries: List[str] = field(default_factory=list)
    keywords_cn: List[str] = field(default_factory=list)
    keywords_en: List[str] = field(default_factory=list)
    related_stage_ids: List[str] = field(default_factory=list)
    related_parameters: List[str] = field(default_factory=list)
    related_problem_ids: List[str] = field(default_factory=list)
    image_search_keywords: List[str] = field(default_factory=list)
    acronym_terms: List[str] = field(default_factory=list)
    source: str = "rule"


@dataclass
class RetrievalResult:
    """retrieve_knowledge() 的输出结构."""
    documents: List[Dict[str, Any]] = field(default_factory=list)
    sop_snippets: List[str] = field(default_factory=list)
    fault_cards: List[Dict[str, Any]] = field(default_factory=list)
    parameter_rules: List[Dict[str, Any]] = field(default_factory=list)
    glossary_entries: List[Dict[str, Any]] = field(default_factory=list)
    plot_interp: List[Dict[str, Any]] = field(default_factory=list)
    image_refs: List[str] = field(default_factory=list)
    source: str = "hybrid"


@dataclass
class SOPReasoning:
    """reason_with_sop() 的输出结构."""
    stage_judgment: str = ""
    problem_analysis: str = ""
    knowledge_basis: List[str] = field(default_factory=list)
    recommended_params: List[Dict[str, Any]] = field(default_factory=list)
    operation_steps: List[str] = field(default_factory=list)
    qc_judgment: str = ""
    decision_options: List[Dict[str, str]] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    next_step_hint: str = ""
    source: str = "rule"


@dataclass
class ComposedAnswer:
    """compose_answer() 的输出结构 — 卡片式结构化回答."""
    current_judgment: str = ""        # 当前判断
    possible_problems: List[str] = field(default_factory=list)  # 可能问题
    suggested_checks: List[str] = field(default_factory=list)   # 建议检查
    param_advice_cryosparc: List[str] = field(default_factory=list)
    param_advice_relion: List[str] = field(default_factory=list)
    related_screenshots: List[str] = field(default_factory=list)
    next_step: str = ""               # 下一步判断
    decision_options: List[Dict[str, str]] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)       # 需补充信息
    formatted_markdown: str = ""      # 最终 Markdown 格式输出
    structured_json: Dict[str, Any] = field(default_factory=dict)
    source: str = "rule"


# ---------------------------------------------------------------------------
# Helper: JSON file loader
# ---------------------------------------------------------------------------

def _load_json_safe(path: str, default: Any = None) -> Any:
    if not path or not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


# ---------------------------------------------------------------------------
# 1. Query Understanding Agent
# ---------------------------------------------------------------------------

class QueryUnderstandingAgent:
    """理解用户自然语言输入：检测阶段、软件、意图、问题类型、缺失信息."""

    # 意图关键词映射
    INTENT_KEYWORDS = {
        "parameter_advice": [
            "参数", "怎么设", "如何设置", "多少合适", "推荐", "建议", "什么值",
            "怎么调", "怎么选", "推荐值", "合适", "设多少",
            "pixel size", "box size", "bfactor", "num_classes", "resolution",
        ],
        "fault_troubleshoot": [
            "不好", "差", "失败", "报错", "问题", "异常", "不对", "有问题",
            "条纹", "噪声", "模糊", "振荡", "偏侧", "垃圾", "拟合差", "不达标",
            "failed", "error", "bad", "wrong", "issue", "problem",
        ],
        "operation_guide": [
            "怎么做", "如何做", "步骤", "操作", "流程", "sop", "标准流程",
            "具体步骤", "详细步骤", "教程", "指导", "指引", "怎么操作",
            "怎么用", "怎么跑",
        ],
        "concept_explain": [
            "是什么", "什么是", "什么意思", "怎么理解", "解释", "含义", "定义",
            "原理", "作用", "影响", "为什么", "概念",
            "what is", "meaning", "definition", "explain",
        ],
        "decision_advice": [
            "选", "还是", "哪个好", "对比", "区别", "选择",
            "cryosparc还是relion", "blob还是topaz", "要不要做",
            "做不做", "需要吗", "必要吗", "够吗", "够不够",
            "能不能", "可不可以", "该不该", "要不要", "cα trace",
            "ca trace", "trace 够", "分辨率不够", "低分辨率建模",
        ],
    }

    # 问题类型关键词映射
    PROBLEM_TYPE_KEYWORDS = {
        "quality_degradation": ["条纹", "噪声", "模糊", "发糊", "不清晰", "看不清"],
        "parameter_error": ["振荡", "波动", "拟合差", "CTF差", "参数错", "设错"],
        "data_limitation": ["偏侧", "取向", "不够", "太少", "优先取向"],
        "classification_issue": ["垃圾", "混入", "分不开", "分类不好", "类太多"],
    }

    # 必需信息清单
    REQUIRED_INFO = {
        "parameter_advice": ["software", "stage"],
        "fault_troubleshoot": ["software", "stage", "symptom"],
        "operation_guide": ["software", "stage"],
        "concept_explain": [],
        "decision_advice": ["stage"],
    }

    def __init__(self, llm: Optional["LLMAgent"] = None, kb_dir: str = _KB_DIR):
        self.llm = llm
        self.kb_dir = kb_dir
        self.stage_synonyms = _load_json_safe(
            os.path.join(kb_dir, "stage_synonyms.json"), {}
        )
        self.problem_synonyms = _load_json_safe(
            os.path.join(kb_dir, "problem_synonyms.json"), {}
        )

    def understand(
        self,
        user_message: str,
        current_stage: str = "",
        current_software: str = "",
        chat_history_summary: str = "",
    ) -> QueryUnderstanding:
        """理解用户查询，返回结构化理解结果（规则匹配模式）.

        navigator 路由已经做了意图识别，此处用规则匹配补充
        阶段/软件/参数/缺失信息。
        """
        return self._understand_with_rules(
            user_message, current_stage, current_software
        )

    def _llm_available(self) -> bool:
        return (
            self.llm is not None
            and getattr(self.llm, "enabled", False)
        )

    def _normalize_stage(self, raw_stage: str, current_stage: str) -> str:
        """把 LLM 返回的阶段描述（cp_XX / 阶段名 / 英文名 / 缩写）归一化为 cp_XX.

        无法识别时回退到当前阶段，避免误判导致阶段识别丢失。
        """
        if not isinstance(self.stage_synonyms, dict):
            return current_stage or ""
        raw = (raw_stage or "").strip().lower()
        if not raw:
            return current_stage or ""
        if raw.startswith("cp_") and raw in self.stage_synonyms:
            return raw
        for cp_id, info in self.stage_synonyms.items():
            if not cp_id.startswith("cp_") or not isinstance(info, dict):
                continue
            candidates = [
                str(info.get("checkpoint_name", "")).lower(),
                str(info.get("checkpoint_cn", "")).lower(),
            ]
            candidates.extend(str(c).lower() for c in info.get("abbreviations", []))
            candidates.extend(str(c).lower() for c in info.get("keywords_cn", []))
            candidates.extend(str(c).lower() for c in info.get("keywords_en", []))
            candidates.extend(str(c).lower() for c in info.get("colloquial", []))
            if raw in candidates:
                return cp_id
        return current_stage or ""

    def _understand_with_rules(
        self,
        user_message: str,
        current_stage: str,
        current_software: str,
    ) -> QueryUnderstanding:
        """规则匹配降级方案."""
        lowered = (user_message or "").lower().strip()

        # 1. 阶段检测
        detected_stage, stage_confidence = self._detect_stage(lowered, current_stage)

        # 2. 软件检测
        detected_software = self._detect_software(lowered, current_software)

        # 3. 意图分类
        user_intent, intent_confidence = self._classify_intent(lowered)

        # 4. 问题类型
        problem_type = self._detect_problem_type(lowered)

        # 5. 提到的参数
        mentioned_params = self._extract_parameters(lowered)

        # 6. 缺失信息判断
        missing_info, should_ask, clarification = self._check_missing_info(
            user_intent, detected_software, detected_stage, lowered
        )

        confidence = (stage_confidence + intent_confidence) / 2.0

        result = QueryUnderstanding(
            detected_stage=detected_stage,
            detected_stage_name=self._stage_name(detected_stage),
            detected_software=detected_software,
            user_intent=user_intent,
            problem_type=problem_type,
            mentioned_parameters=mentioned_params,
            missing_information=missing_info,
            confidence=confidence,
            should_ask_clarification=should_ask,
            clarification_questions=clarification,
            source="rule",
        )
        self._apply_intent_flags(result)
        return result

    def _detect_stage(self, lowered: str, current_stage: str) -> Tuple[str, float]:
        """检测用户提到的阶段，返回 (stage_id, confidence)."""
        if not isinstance(self.stage_synonyms, dict):
            return current_stage, 0.3

        best_stage = current_stage or ""
        best_score = 0.3 if current_stage else 0.0

        for key, info in self.stage_synonyms.items():
            if not isinstance(info, dict) or key.startswith("_"):
                continue
            cp_id = info.get("checkpoint_name", key) if key.startswith("cp_") else key
            if not key.startswith("cp_"):
                continue
            score = 0.0
            for kw in info.get("keywords_cn", []):
                if kw and kw.lower() in lowered:
                    score += 0.4
            for kw in info.get("keywords_en", []):
                if kw and kw.lower() in lowered:
                    score += 0.3
            for kw in info.get("colloquial", []):
                if kw and kw.lower() in lowered:
                    score += 0.35
            # 当前阶段加分（用户在某个阶段问问题，大概率问的是当前阶段）
            if key == current_stage and score == 0:
                score = 0.2
            if score > best_score:
                best_score = min(score, 0.95)
                best_stage = key

        return best_stage, best_score

    def _detect_software(self, lowered: str, current_software: str) -> str:
        if "cryosparc" in lowered or "csparc" in lowered:
            return "cryosparc"
        if "relion" in lowered:
            return "relion"
        return current_software

    def _classify_intent(self, lowered: str) -> Tuple[str, float]:
        scores: Dict[str, float] = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw.lower() in lowered:
                    score += 0.3
            scores[intent] = min(score, 0.95)

        # Tie-break by explicit question shape so incidental shared keywords do
        # not route "why/what" questions into operation or parameter answers.
        if any(k in lowered for k in ("why", "what is", "meaning", "definition", "explain", "原理", "作用", "影响")):
            scores["concept_explain"] = min(scores.get("concept_explain", 0.0) + 0.35, 0.95)
        if any(k in lowered for k in ("step", "sop", "workflow", "操作", "步骤", "流程", "怎么做", "如何做")):
            scores["operation_guide"] = min(scores.get("operation_guide", 0.0) + 0.35, 0.95)
        if any(k in lowered for k in ("parameter", "setting", "value", "threshold", "参数", "设置", "阈值", "推荐")):
            scores["parameter_advice"] = min(scores.get("parameter_advice", 0.0) + 0.35, 0.95)
        if any(k in lowered for k in ("error", "failed", "bad", "wrong", "报错", "失败", "异常", "不对", "不好")):
            scores["fault_troubleshoot"] = min(scores.get("fault_troubleshoot", 0.0) + 0.4, 0.95)

        if not scores or max(scores.values()) == 0:
            return "operation_guide", 0.2

        best = max(scores, key=scores.get)
        return best, scores[best]

    def _detect_problem_type(self, lowered: str) -> str:
        for ptype, keywords in self.PROBLEM_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in lowered:
                    return ptype
        return ""

    def _extract_parameters(self, lowered: str) -> List[str]:
        params_found = []
        param_patterns = {
            "pixel_size": ["pixel size", "像素尺寸", "a/pix", "angstrom per pixel"],
            "box_size": ["box size", "盒子大小", "box"],
            "bfactor": ["b-factor", "b因子", "bfactor"],
            "num_classes": ["num_classes", "类别数", "分类数", "number of classes"],
            "max_resolution": ["max resolution", "最大分辨率", "maximum resolution"],
            "defocus": ["defocus", "离焦"],
            "voltage": ["voltage", "电压", "kv"],
            "symmetry": ["symmetry", "对称"],
            "dose": ["dose", "剂量"],
        }
        for param, patterns in param_patterns.items():
            for p in patterns:
                if p.lower() in lowered:
                    params_found.append(param)
                    break
        return params_found

    def _check_missing_info(
        self,
        intent: str,
        software: str,
        stage: str,
        lowered: str,
    ) -> Tuple[List[str], bool, List[str]]:
        required = self.REQUIRED_INFO.get(intent, [])
        missing = []
        questions = []

        if "software" in required and not software:
            missing.append("software")
            questions.append("你使用的是 cryoSPARC 还是 RELION？")
        if "stage" in required and not stage:
            missing.append("stage")
            questions.append("你目前在哪个处理阶段？")
        if "symptom" in required:
            has_symptom = any(
                kw in lowered
                for kw in ["不好", "差", "失败", "报错", "条纹", "模糊", "振荡", "偏侧"]
            )
            if not has_symptom:
                missing.append("symptom")
                questions.append("请描述你遇到的具体问题或异常现象。")

        should_ask = len(missing) > 0 and len(questions) <= 2
        return missing, should_ask, questions[:2]

    def _apply_intent_flags(self, result: QueryUnderstanding) -> None:
        intent = result.user_intent
        result.needs_sop = intent in ("operation_guide", "decision_advice")
        result.needs_parameter_advice = intent in ("parameter_advice", "decision_advice")
        result.needs_qc_judgement = intent == "fault_troubleshoot"
        result.needs_fault_diagnosis = intent == "fault_troubleshoot"
        result.needs_image_match = intent in ("fault_troubleshoot", "operation_guide")

    def _stage_name(self, stage_id: str) -> str:
        if not stage_id or not isinstance(self.stage_synonyms, dict):
            return ""
        info = self.stage_synonyms.get(stage_id, {})
        return info.get("checkpoint_cn", "") if isinstance(info, dict) else ""


# ---------------------------------------------------------------------------
# 2. Query Expansion Agent
# ---------------------------------------------------------------------------

class QueryExpansionAgent:
    """查询扩展：把口语化问题扩展为中英文关键词 + stage_id + parameter_id."""

    def __init__(self, llm: Optional["LLMAgent"] = None, kb_dir: str = _KB_DIR):
        self.llm = llm
        self.kb_dir = kb_dir
        self.stage_synonyms = _load_json_safe(
            os.path.join(kb_dir, "stage_synonyms.json"), {}
        )
        self.problem_synonyms = _load_json_safe(
            os.path.join(kb_dir, "problem_synonyms.json"), {}
        )
        self.metadata_index = _load_json_safe(
            os.path.join(kb_dir, "metadata_index.json"), {}
        )
        # 缩写映射表：用于把口语/缩写扩展为全称关键词（概念问答的关键兜底）。
        self.acronym_map = _load_json_safe(
            os.path.join(kb_dir, "terminology", "acronym_map.json"), {}
        )
        if not isinstance(self.acronym_map, dict):
            self.acronym_map = {}
        # 内置保底缩写表：即使 acronym_map.json 缺失，也能扩展常见 cryo-EM 缩写。
        self._DEFAULT_ACRONYM_MAP = {
            "eer": "EER Electron Event Representation Falcon4i",
            "ctf": "CTF Contrast Transfer Function",
            "cs": "Cs spherical aberration",
            "mrc": "MRC Micrograph Image Format",
            "mrcs": "MRCS particle stack",
            "star": "STAR Self-defining Text Archiving Retrieval",
            "fsc": "FSC Fourier Shell Correlation",
            "bfactor": "B-factor sharpening",
            "mtf": "MTF Modulation Transfer Function",
            "snr": "SNR Signal-to-Noise Ratio",
            "dose": "electron dose dose-rate",
            "sparc": "SPARC cryoSPARC",
            "abinitio": "ab-initio initial model",
            "2d": "2D two dimensional classification",
            "3d": "3D three dimensional refinement",
        }

    def expand(
        self,
        user_message: str,
        understanding: QueryUnderstanding,
    ) -> QueryExpansion:
        """扩展查询，返回结构化扩展结果（规则模式：同义词+缩写扩展）."""
        return self._expand_with_rules(user_message, understanding)

    def _llm_available(self) -> bool:
        return self.llm is not None and getattr(self.llm, "enabled", False)

    def _compute_acronym_terms(self, user_message: str) -> List[str]:
        """把用户问题中的常见 cryo-EM 缩写扩展为全称关键词。

        合并 acronym_map.json 与内置 _DEFAULT_ACRONYM_MAP 保底表，
        用词边界匹配，避免把 'score' 误命中 'cs'。
        """
        lowered = (user_message or "").lower()
        merged: Dict[str, str] = {}
        merged.update(self._DEFAULT_ACRONYM_MAP)
        if isinstance(self.acronym_map, dict):
            for k, v in self.acronym_map.items():
                if isinstance(k, str) and k:
                    merged[k.lower()] = v if isinstance(v, str) else str(v)
        hits: List[str] = []
        for acr, full in merged.items():
            if not acr:
                continue
            if re.search(rf"\b{re.escape(acr)}\b", lowered):
                hits.append(full)
        # 去重（大小写不敏感）
        seen = set()
        out: List[str] = []
        for h in hits:
            key = h.lower()
            if key not in seen:
                seen.add(key)
                out.append(h)
        return out[:8]

    def _expand_with_rules(
        self, user_message: str, understanding: QueryUnderstanding
    ) -> QueryExpansion:
        """规则扩展降级方案."""
        lowered = (user_message or "").lower()
        keywords_cn: List[str] = []
        keywords_en: List[str] = []
        related_stages: List[str] = []
        related_params: List[str] = list(understanding.mentioned_parameters)
        related_problems: List[str] = []
        image_keywords: List[str] = []
        acronym_terms: List[str] = self._compute_acronym_terms(user_message)

        # 从 stage_synonyms 提取关键词
        if isinstance(self.stage_synonyms, dict):
            stage_info = self.stage_synonyms.get(understanding.detected_stage, {})
            if isinstance(stage_info, dict):
                keywords_cn.extend(stage_info.get("keywords_cn", [])[:5])
                keywords_en.extend(stage_info.get("keywords_en", [])[:5])
                related_stages.append(understanding.detected_stage) if understanding.detected_stage else None
                related_params.extend(stage_info.get("key_params", []))

        # 从 problem_synonyms 提取关键词
        if isinstance(self.problem_synonyms, dict):
            for pid, pinfo in self.problem_synonyms.items():
                if not isinstance(pinfo, dict) or pid.startswith("_"):
                    continue
                matched = False
                for kw in pinfo.get("keywords_cn", []):
                    if kw and kw.lower() in lowered:
                        matched = True
                        break
                if not matched:
                    for kw in pinfo.get("keywords_en", []):
                        if kw and kw.lower() in lowered:
                            matched = True
                            break
                if matched:
                    related_problems.append(pinfo.get("fault_id", pid))
                    keywords_cn.extend(pinfo.get("keywords_cn", [])[:3])
                    keywords_en.extend(pinfo.get("keywords_en", [])[:3])
                    related_stages.append(pinfo.get("related_stage", ""))

        # 图片搜索关键词
        if understanding.needs_image_match:
            stage_info = self.stage_synonyms.get(understanding.detected_stage, {}) if isinstance(self.stage_synonyms, dict) else {}
            if isinstance(stage_info, dict):
                image_keywords.append(stage_info.get("checkpoint_cn", ""))
            if understanding.problem_type:
                image_keywords.append(understanding.problem_type)

        # 构建检索查询
        search_queries = [user_message]
        if keywords_en:
            search_queries.append(" ".join(keywords_en[:5]))
        if keywords_cn:
            search_queries.append(" ".join(keywords_cn[:5]))
        if acronym_terms:
            search_queries.append(" ".join(acronym_terms[:5]))
            keywords_en.extend(acronym_terms[:3])

        # 去重
        related_stages = list(set(s for s in related_stages if s))
        related_params = list(set(related_params))
        related_problems = list(set(related_problems))
        keywords_cn = list(set(keywords_cn))
        keywords_en = list(set(keywords_en))

        return QueryExpansion(
            search_queries=search_queries,
            keywords_cn=keywords_cn,
            keywords_en=keywords_en,
            related_stage_ids=related_stages,
            related_parameters=related_params,
            related_problem_ids=related_problems,
            image_search_keywords=[k for k in image_keywords if k],
            acronym_terms=acronym_terms,
            source="rule",
        )


# ---------------------------------------------------------------------------
# 3. RAG Retrieval Optimizer
# ---------------------------------------------------------------------------

class RAGRetrievalOptimizer:
    """混合检索优化：keyword search + vector search + metadata filter."""

    def __init__(
        self,
        retriever: Any = None,
        navigator: Any = None,
        kb_dir: str = _KB_DIR,
    ):
        self.retriever = retriever
        self.navigator = navigator
        self.kb_dir = kb_dir
        self.metadata_index = _load_json_safe(
            os.path.join(kb_dir, "metadata_index.json"), {}
        )
        self.checkpoints = _load_json_safe(
            os.path.join(kb_dir, "flows", "pipeline_checkpoints.json"),
            _load_json_safe(os.path.join(kb_dir, "pipeline_checkpoints.json"), [])
        )
        self.faults = _load_json_safe(
            os.path.join(kb_dir, "faults", "fault_trouble.json"),
            _load_json_safe(os.path.join(kb_dir, "fault_trouble.json"), [])
        )
        self.rules = _load_json_safe(
            os.path.join(kb_dir, "rules", "tier2_rules.json"),
            _load_json_safe(os.path.join(kb_dir, "tier2_rules.json"), [])
        )
        # 术语库：健壮加载，过滤掉非 dict 或缺少 term 的脏数据，
        # 避免 _match_glossary 在脏条目上抛错。
        raw_glossary = _load_json_safe(
            os.path.join(kb_dir, "terminology", "glossary.json"), []
        )
        if isinstance(raw_glossary, list):
            self.glossary = [
                g for g in raw_glossary
                if isinstance(g, dict) and (g.get("term") or "").strip()
            ]
        else:
            self.glossary = []

    def retrieve(
        self,
        understanding: QueryUnderstanding,
        expansion: QueryExpansion,
    ) -> RetrievalResult:
        """执行混合检索，返回结构化检索结果."""
        result = RetrievalResult()

        # 1. 向量/关键词检索（通过现有 retriever）
        if self.retriever:
            # 性能优化：将最多 3 条扩展查询合并为一次检索（top_k 提高到 8 保留多 query 召回），
            # 避免对 search_queries[:3] 串行调用 3 次 retriever.search 造成的 3 倍网络往返。
            combined_query = " ".join(expansion.search_queries[:3]).strip()
            if not combined_query and expansion.search_queries:
                combined_query = expansion.search_queries[0]
            try:
                docs = self.retriever.search(combined_query, top_k=8) if combined_query else []
                seen_doc = set()
                for doc_id, text, score in docs:
                    if doc_id in seen_doc:
                        continue
                    seen_doc.add(doc_id)
                    result.documents.append({
                        "doc_id": doc_id,
                        "text": text,
                        "score": score,
                        "source_type": "vector",
                    })
            except Exception:
                pass

        # 2. 阶段约束检索：直接从 checkpoints 取当前阶段的 SOP
        stage_id = understanding.detected_stage
        if stage_id:
            sop_snippet = self._get_stage_sop(stage_id, understanding.detected_software)
            if sop_snippet:
                result.sop_snippets.append(sop_snippet)

        # 3. 故障卡检索：根据问题类型和关键词匹配
        if understanding.needs_fault_diagnosis or expansion.related_problem_ids:
            fault_cards = self._match_fault_cards(
                expansion.related_problem_ids,
                " ".join(expansion.keywords_cn + expansion.keywords_en),
            )
            result.fault_cards.extend(fault_cards)

        # 4. 参数规则检索
        if understanding.needs_parameter_advice and expansion.related_parameters:
            param_rules = self._match_param_rules(
                expansion.related_parameters,
                stage_id,
                understanding.detected_software,
            )
            result.parameter_rules.extend(param_rules)

        # 概念问答（concept_explain）由 SmartQAEngine.answer_concept 直接走
        # _match_glossary，不经过 retrieve，故此处不再检索术语库（避免死分支）。

        # 5. 图片引用
        if understanding.needs_image_match:
            result.image_refs = self._get_image_refs(stage_id, understanding.problem_type)

        return result

    def _get_stage_sop(self, stage_id: str, software: str) -> str:
        """从 checkpoints 获取当前阶段的 SOP 文本."""
        if not isinstance(self.checkpoints, list):
            return ""
        for cp in self.checkpoints:
            if not isinstance(cp, dict):
                continue
            if cp.get("checkpoint_id") != stage_id:
                continue
            sw = software if software in ("cryosparc", "relion") else "cryosparc"
            guide = cp.get(sw, cp.get("cryosparc", {}))
            steps = guide.get("key_steps", []) if isinstance(guide, dict) else []
            qc = cp.get("qc_check", [])
            pitfalls = cp.get("common_pitfalls", [])
            parts = [
                f"## {cp.get('checkpoint_cn', stage_id)}",
                f"目标: {cp.get('stage_goal', '')}",
            ]
            if steps:
                parts.append("步骤: " + "; ".join(str(s) for s in steps[:5]))
            if qc:
                parts.append("QC: " + "; ".join(str(q) for q in qc[:3]))
            if pitfalls:
                parts.append("常见坑: " + "; ".join(str(p) for p in pitfalls[:3]))
            return "\n".join(parts)
        return ""

    def _match_fault_cards(
        self, problem_ids: List[str], keywords: str
    ) -> List[Dict[str, Any]]:
        """匹配故障卡."""
        if not isinstance(self.faults, list):
            return []
        lowered = (keywords or "").lower()
        matched: List[Dict[str, Any]] = []
        for fault in self.faults:
            if not isinstance(fault, dict):
                continue
            fid = fault.get("fault_id", "")
            if fid in problem_ids:
                matched.append(fault)
                continue
            # 关键词匹配
            all_kw = [fault.get("fault_keyword", "")]
            all_kw.extend(fault.get("fault_keywords", []))
            for kw in all_kw:
                if kw and kw.lower() in lowered:
                    matched.append(fault)
                    break
        return matched[:3]

    def _match_param_rules(
        self,
        params: List[str],
        stage_id: str,
        software: str,
    ) -> List[Dict[str, Any]]:
        """匹配参数规则."""
        rules: List[Dict[str, Any]] = []
        # 从 tier2_rules.json 匹配
        if isinstance(self.rules, list):
            for rule in self.rules:
                if not isinstance(rule, dict):
                    continue
                condition = rule.get("condition", "").lower()
                for param in params:
                    if param.lower() in condition:
                        rules.append(rule)
                        break

        # 从 metadata_index 的 parameters 提取参数信息
        if isinstance(self.metadata_index, dict):
            param_index = self.metadata_index.get("parameters", {})
            for param in params:
                pinfo = param_index.get(param, {})
                if pinfo:
                    rules.append({
                        "parameter": param,
                        "description_cn": pinfo.get("description_cn", ""),
                        "aliases": pinfo.get("aliases", []),
                        "stages": pinfo.get("stages", []),
                    })

        # 从 checkpoints 提取该阶段该软件的关键参数
        if stage_id and isinstance(self.checkpoints, list):
            sw = software if software in ("cryosparc", "relion") else "cryosparc"
            for cp in self.checkpoints:
                if cp.get("checkpoint_id") == stage_id:
                    guide = cp.get(sw, cp.get("cryosparc", {}))
                    if isinstance(guide, dict):
                        key_params = guide.get("key_params", [])
                        for kp in key_params:
                            if kp in params:
                                rules.append({
                                    "parameter": kp,
                                    "stage": stage_id,
                                    "software": sw,
                                    "source": "checkpoint_key_params",
                                })
                    break

        return rules[:5]

    @staticmethod
    def _term_in_text(term: str, text: str) -> bool:
        """term 是否命中 text（词边界感知）.

        - 纯 ASCII 词（如 eer / ctf / fsc）：用 ``(?<![a-z0-9])term(?![a-z0-9])``
          词边界，避免 "eer" 误命中 "engineer" / "cheer" 等长词中的子串；
        - 含非 ASCII（中文术语如 像素尺寸 / 分辨率）：保持子串匹配，
          因为中文没有词边界概念。
        """
        if not term:
            return False
        if re.fullmatch(r"[a-z0-9_.+\-]+", term):
            pat = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
            return bool(re.search(pat, text))
        return term in text

    def _match_glossary(
        self,
        keywords: str,
        raw_user_text: str = "",
        acronym_terms: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """匹配术语表.

        匹配优先级（任一命中即收录）：
          1) 原始用户输入子串命中 term / alias（如 "eer是什么文件" 命中 term "eer"）；
          2) 缩写全称命中（如 acronym "EER Electron Event Representation" 命中 term "eer"）；
          3) 兜底：扩展关键词命中 term / alias。
        这样概念问答不再依赖 expansion 是否产出关键词，从根本上修复
        "概念问题 expansion 关键词为空 → 传空串 → 永不匹配" 的断链。
        """
        if not isinstance(self.glossary, list):
            return []
        lowered_kw = (keywords or "").lower()
        lowered_raw = (raw_user_text or "").lower()
        acr = acronym_terms or []
        matched: List[Dict[str, Any]] = []
        for item in self.glossary:
            if not isinstance(item, dict):
                continue
            term = (item.get("term") or "").lower()
            aliases = [str(a).lower() for a in item.get("aliases", [])]
            hit = False
            # 1) 原始文本命中（词边界感知）
            if self._term_in_text(term, lowered_raw):
                hit = True
            if not hit:
                for alias in aliases:
                    if self._term_in_text(alias, lowered_raw):
                        hit = True
                        break
            # 2) 缩写全称命中（term / alias 出现在某个缩写全称里，取词边界）
            if not hit and acr:
                for a in acr:
                    a_low = a.lower()
                    if self._term_in_text(term, a_low):
                        hit = True
                        break
                    if not hit:
                        for alias in aliases:
                            if self._term_in_text(alias, a_low):
                                hit = True
                                break
                    if hit:
                        break
            # 3) 关键词兜底
            if not hit and self._term_in_text(term, lowered_kw):
                hit = True
            if not hit:
                for alias in aliases:
                    if self._term_in_text(alias, lowered_kw):
                        hit = True
                        break
            if hit:
                matched.append(item)
        return matched[:3]

    def _get_image_refs(
        self, stage_id: str, problem_type: str
    ) -> List[str]:
        """获取相关图片引用（目前返回描述性引用，未来可扩展为实际图片路径）."""
        refs: List[str] = []
        if stage_id and isinstance(self.checkpoints, list):
            for cp in self.checkpoints:
                if cp.get("checkpoint_id") == stage_id:
                    image_refs = cp.get("image_refs", [])
                    if image_refs:
                        refs.extend(str(r) for r in image_refs)
                    # QC 图表参考
                    qc = cp.get("qc_check", [])
                    if qc:
                        refs.append(f"{cp.get('checkpoint_cn', '')} QC 检查图")
                    break
        if problem_type:
            refs.append(f"问题类型: {problem_type} 相关截图")
        return refs[:5]


# ---------------------------------------------------------------------------
# 4. SOP Reasoning Agent
# ---------------------------------------------------------------------------

class SOPReasoningAgent:
    """SOP 推理：结合检索结果 + 用户上下文推理."""

    def __init__(self, llm: Optional["LLMAgent"] = None, kb_dir: str = _KB_DIR):
        self.llm = llm
        self.kb_dir = kb_dir
        self.checkpoints = _load_json_safe(
            os.path.join(kb_dir, "flows", "pipeline_checkpoints.json"),
            _load_json_safe(os.path.join(kb_dir, "pipeline_checkpoints.json"), [])
        )

    def reason(
        self,
        understanding: QueryUnderstanding,
        expansion: QueryExpansion,
        retrieval: RetrievalResult,
        current_software: str = "",
    ) -> SOPReasoning:
        """结合检索结果和用户上下文进行推理（规则模式）.

        RAG 检索结果 + 规则模板推理；最终回答质量由 _polish_reply 中的
        LLM rewrite 保证。
        """
        return self._reason_with_rules(understanding, expansion, retrieval, current_software)

    def _llm_available(self) -> bool:
        return self.llm is not None and getattr(self.llm, "enabled", False)

    def _reason_with_rules(
        self,
        understanding: QueryUnderstanding,
        expansion: QueryExpansion,
        retrieval: RetrievalResult,
        current_software: str,
    ) -> SOPReasoning:
        """规则推理降级方案."""
        reasoning = SOPReasoning(source="rule")

        # 阶段判断
        if understanding.detected_stage:
            cp = self._get_checkpoint(understanding.detected_stage)
            if cp:
                reasoning.stage_judgment = (
                    f"当前阶段：{cp.get('checkpoint_cn', understanding.detected_stage)} "
                    f"（{cp.get('stage_goal', '')}）"
                )

        # 问题分析
        if understanding.problem_type:
            type_map = {
                "quality_degradation": "检测到质量问题——结果质量下降",
                "parameter_error": "检测到参数错误——可能参数设置不当",
                "data_limitation": "检测到数据限制——可能数据本身存在不足",
                "classification_issue": "检测到分类问题——分类结果不理想",
            }
            reasoning.problem_analysis = type_map.get(understanding.problem_type, "")

        if retrieval.fault_cards:
            for fc in retrieval.fault_cards[:2]:
                reasoning.problem_analysis += f"\n- {fc.get('title_cn', '')}: {fc.get('symptom_cn', '')}"

        # 知识依据
        if retrieval.sop_snippets:
            reasoning.knowledge_basis.append("SOP 文档")
        if retrieval.fault_cards:
            reasoning.knowledge_basis.append("故障排查卡")
        if retrieval.parameter_rules:
            reasoning.knowledge_basis.append("参数规则库")
        if retrieval.glossary_entries:
            reasoning.knowledge_basis.append("术语表")

        # 推荐参数
        sw = current_software if current_software in ("cryosparc", "relion") else "cryosparc"
        if understanding.needs_parameter_advice:
            for pr in retrieval.parameter_rules:
                if isinstance(pr, dict) and pr.get("parameter"):
                    reasoning.recommended_params.append({
                        "param": pr.get("parameter", ""),
                        "value": pr.get("value", "见知识库推荐"),
                        "reason": pr.get("reason", pr.get("description_cn", "")),
                    })

        # 操作步骤
        if retrieval.sop_snippets:
            for snippet in retrieval.sop_snippets[:1]:
                lines = snippet.split("\n")
                for line in lines:
                    if line.strip().startswith("步骤:"):
                        steps_text = line.replace("步骤:", "").strip()
                        reasoning.operation_steps = [s.strip() for s in steps_text.split(";") if s.strip()]

        # 质控判断
        cp = self._get_checkpoint(understanding.detected_stage) if understanding.detected_stage else None
        if cp and isinstance(cp, dict):
            qc = cp.get("qc_check", [])
            if qc:
                reasoning.qc_judgment = "；".join(str(q) for q in qc[:3])

        # 决策选项
        if understanding.user_intent == "decision_advice":
            cp = self._get_checkpoint(understanding.detected_stage) if understanding.detected_stage else None
            if cp and isinstance(cp, dict):
                dt = cp.get("decision_tree", {})
                if isinstance(dt, dict):
                    for rec_key, rec_val in dt.get("recommendations", {}).items():
                        if isinstance(rec_val, dict):
                            reasoning.decision_options.append({
                                "option": rec_val.get("picker", rec_key),
                                "reason": rec_val.get("reason", ""),
                            })

        # 风险提示
        if cp and isinstance(cp, dict):
            pitfalls = cp.get("common_pitfalls", [])
            reasoning.risk_warnings = [str(p) for p in pitfalls[:3]]

        # 下一步提示
        if understanding.user_intent == "fault_troubleshoot" and retrieval.fault_cards:
            fc = retrieval.fault_cards[0]
            solutions = fc.get("solutions", []) if isinstance(fc, dict) else []
            if solutions and isinstance(solutions, list):
                first = solutions[0] if isinstance(solutions[0], dict) else {}
                reasoning.next_step_hint = first.get("action_cn", "请按故障卡建议排查")
        elif understanding.user_intent == "operation_guide":
            reasoning.next_step_hint = "按上述步骤操作，完成后告诉我结果。"
        elif understanding.user_intent == "parameter_advice":
            reasoning.next_step_hint = "按推荐参数设置后运行，观察结果。"

        return reasoning

    def _get_checkpoint(self, stage_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(self.checkpoints, list):
            return None
        for cp in self.checkpoints:
            if isinstance(cp, dict) and cp.get("checkpoint_id") == stage_id:
                return cp
        return None


# ---------------------------------------------------------------------------
# 5. Answer Composer Agent
# ---------------------------------------------------------------------------

class AnswerComposerAgent:
    """回答整合：将推理结果组装为卡片式结构化回答."""

    def __init__(self, llm: Optional["LLMAgent"] = None, kb_dir: str = _KB_DIR):
        self.llm = llm
        self.kb_dir = kb_dir

    def compose(
        self,
        understanding: QueryUnderstanding,
        reasoning: SOPReasoning,
        retrieval: RetrievalResult,
        current_software: str = "",
        response_profile: str = "teaching",
    ) -> ComposedAnswer:
        """组装卡片式结构化回答."""
        answer = ComposedAnswer()

        # 当前判断
        answer.current_judgment = reasoning.stage_judgment or (
            f"已检测到你在咨询{understanding.detected_stage_name or 'cryo-EM处理'}相关问题。"
        )

        # 可能问题
        if reasoning.problem_analysis:
            problem_lines = reasoning.problem_analysis.split("\n")
            answer.possible_problems = [l.strip("- ") for l in problem_lines if l.strip()]

        # 建议检查
        if reasoning.qc_judgment:
            answer.suggested_checks = reasoning.qc_judgment.split("；")

        # 参数建议（分软件）
        sw = current_software if current_software in ("cryosparc", "relion") else "cryosparc"
        for rec in reasoning.recommended_params:
            param_str = f"**{rec.get('param', '')}**: {rec.get('value', '')}（{rec.get('reason', '')}）"
            if sw == "cryosparc":
                answer.param_advice_cryosparc.append(param_str)
            else:
                answer.param_advice_relion.append(param_str)
        # 如果没有分软件的参数建议，但推理有推荐参数，同时填入两个列表
        if not answer.param_advice_cryosparc and not answer.param_advice_relion:
            for rec in reasoning.recommended_params:
                param_str = f"**{rec.get('param', '')}**: {rec.get('value', '')}（{rec.get('reason', '')}）"
                answer.param_advice_cryosparc.append(param_str)
                answer.param_advice_relion.append(param_str)

        # 相关截图
        answer.related_screenshots = retrieval.image_refs

        # 下一步判断
        answer.next_step = reasoning.next_step_hint or "请根据上述建议操作，完成后告诉我结果。"

        # 决策选项
        answer.decision_options = reasoning.decision_options

        # 需补充信息
        if understanding.should_ask_clarification:
            answer.missing_info = understanding.clarification_questions
        else:
            answer.missing_info = understanding.missing_information

        # 风险提示加入可能的补充
        if reasoning.risk_warnings:
            answer.possible_problems.extend(
                f"⚠️ {w}" for w in reasoning.risk_warnings[:2]
            )

        # 生成 Markdown
        response_profile = normalize_response_profile(response_profile)
        response_focus = self._focus_from_understanding(understanding)
        base_markdown = self._to_markdown(answer, understanding, reasoning)
        answer.formatted_markdown = format_response_for_profile(
            base_markdown,
            response_profile,
            evidence_hint="；".join(reasoning.knowledge_basis[:4]),
        )
        answer.structured_json = self._to_structured_json(answer, understanding, reasoning)
        answer.structured_json["response_profile"] = response_profile
        answer.structured_json["response_focus"] = response_focus
        answer.source = reasoning.source

        return answer

    def _focus_from_understanding(self, understanding: QueryUnderstanding) -> str:
        intent_focus = {
            "parameter_advice": "parameter",
            "fault_troubleshoot": "troubleshooting",
            "operation_guide": "operation",
            "concept_explain": "concept",
            "decision_advice": "decision",
        }
        if understanding.needs_image_match:
            return "multimodal"
        return intent_focus.get(
            understanding.user_intent,
            detect_response_focus("", understanding.user_intent),
        )

    def _to_markdown(
        self,
        answer: ComposedAnswer,
        understanding: QueryUnderstanding,
        reasoning: SOPReasoning,
    ) -> str:
        """生成卡片式 Markdown 回答."""
        lines: List[str] = []

        # 标题
        intent_labels = {
            "parameter_advice": "参数建议",
            "fault_troubleshoot": "故障排查",
            "operation_guide": "操作指导",
            "concept_explain": "概念解释",
            "decision_advice": "决策建议",
        }
        label = intent_labels.get(understanding.user_intent, "智能问答")
        lines.append(f"## 🧠 {label}")
        lines.append("")

        # 当前判断
        if answer.current_judgment:
            lines.append(f"**当前判断**: {answer.current_judgment}")
            lines.append("")

        # 可能问题
        if answer.possible_problems:
            lines.append("**可能问题**:")
            for p in answer.possible_problems:
                lines.append(f"- {p}")
            lines.append("")

        # 建议检查
        if answer.suggested_checks:
            lines.append("**建议检查**:")
            for c in answer.suggested_checks:
                lines.append(f"- {c}")
            lines.append("")

        # 参数建议
        if answer.param_advice_cryosparc or answer.param_advice_relion:
            lines.append("**参数建议**:")
            if answer.param_advice_cryosparc:
                lines.append("*cryoSPARC*:")
                for p in answer.param_advice_cryosparc:
                    lines.append(f"- {p}")
            if answer.param_advice_relion:
                lines.append("*RELION*:")
                for p in answer.param_advice_relion:
                    lines.append(f"- {p}")
            lines.append("")

        # 操作步骤
        if reasoning.operation_steps:
            lines.append("**操作方案**:")
            for i, step in enumerate(reasoning.operation_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        # 相关截图
        if answer.related_screenshots:
            lines.append("**相关截图**:")
            for s in answer.related_screenshots:
                lines.append(f"- {s}")
            lines.append("")

        # 下一步判断
        if answer.next_step:
            lines.append(f"**下一步**: {answer.next_step}")
            lines.append("")

        # 决策选项
        if answer.decision_options:
            lines.append("**决策选项**:")
            for opt in answer.decision_options:
                lines.append(f"- {opt.get('option', '')}: {opt.get('reason', '')}")
            lines.append("")

        # 需补充信息
        if answer.missing_info:
            lines.append("**需补充信息**:")
            for q in answer.missing_info:
                lines.append(f"- ❓ {q}")
            lines.append("")

        return "\n".join(lines)

    def _to_structured_json(
        self,
        answer: ComposedAnswer,
        understanding: QueryUnderstanding,
        reasoning: SOPReasoning,
    ) -> Dict[str, Any]:
        """生成结构化 JSON（供 UI 域适配卡片结构）."""
        return {
            "card_type": "smart_qa",
            "intent": understanding.user_intent,
            "response_focus": self._focus_from_understanding(understanding),
            "stage": understanding.detected_stage,
            "software": understanding.detected_software,
            "confidence": understanding.confidence,
            "sections": {
                "current_judgment": answer.current_judgment,
                "possible_problems": answer.possible_problems,
                "suggested_checks": answer.suggested_checks,
                "param_advice": {
                    "cryosparc": answer.param_advice_cryosparc,
                    "relion": answer.param_advice_relion,
                },
                "operation_steps": reasoning.operation_steps,
                "related_screenshots": answer.related_screenshots,
                "next_step": answer.next_step,
                "decision_options": answer.decision_options,
                "missing_info": answer.missing_info,
                "risk_warnings": reasoning.risk_warnings,
            },
            "knowledge_sources": reasoning.knowledge_basis,
            "source": understanding.source,
        }


# ---------------------------------------------------------------------------
# Smart QA Engine — Main Orchestrator
# ---------------------------------------------------------------------------

class SmartQAEngine:
    """智能问答调度引擎 — 编排五段式管线.

    用法：
        engine = SmartQAEngine(llm=app.llm, retriever=app.retriever, navigator=app.navigator)
        result = engine.process(user_text, state)

    result 包含：
        - understanding: QueryUnderstanding
        - expansion: QueryExpansion
        - retrieval: RetrievalResult
        - reasoning: SOPReasoning
        - answer: ComposedAnswer
        - enhanced_context: str (注入到 _polish_reply 的增强上下文)
        - structured_cards: Dict (供 UI 域使用)
        - timing_ms: Dict (供性能域使用)
    """

    def __init__(
        self,
        llm: Optional["LLMAgent"] = None,
        retriever: Any = None,
        navigator: Any = None,
        kb_dir: str = _KB_DIR,
    ):
        self.llm = llm
        self.kb_dir = kb_dir
        self.understanding_agent = QueryUnderstandingAgent(llm=llm, kb_dir=kb_dir)
        self.expansion_agent = QueryExpansionAgent(llm=llm, kb_dir=kb_dir)
        self.retrieval_optimizer = RAGRetrievalOptimizer(
            retriever=retriever, navigator=navigator, kb_dir=kb_dir
        )
        self.reasoning_agent = SOPReasoningAgent(llm=llm, kb_dir=kb_dir)
        self.composer = AnswerComposerAgent(llm=llm, kb_dir=kb_dir)

    def understand_and_expand(
        self,
        user_text: str,
        current_stage: str = "",
        current_software: str = "",
        chat_history_summary: str = "",
    ) -> Tuple[QueryUnderstanding, QueryExpansion]:
        """合并理解 + 扩展为单一阶段（规则模式，零 LLM 调用）.

        一次完成意图识别 + 查询扩展，减少主流程的函数调用与 try/except 开销。
        返回 (understanding, expansion) 元组，保持与原 understand() + expand()
        串行调用完全兼容的返回值。

        性能说明：understand 与 expand 均为规则模式（不调 LLM），合并后仍为
        规则模式；对 concept_explain 快速通道，expansion 会被丢弃但开销可忽略。
        """
        # 阶段 1：理解（规则模式）
        try:
            understanding = self.understanding_agent.understand(
                user_text, current_stage, current_software, chat_history_summary
            )
        except Exception:
            understanding = QueryUnderstanding(
                detected_stage=current_stage,
                detected_software=current_software,
                confidence=0.0,
                source="rule",
            )

        # 阶段 2：扩展（规则模式，依赖 understanding 结果）
        try:
            expansion = self.expansion_agent.expand(user_text, understanding)
        except Exception:
            expansion = QueryExpansion(search_queries=[user_text], source="rule")

        return understanding, expansion

    def process(
        self,
        user_text: str,
        state: "PipelineState",
        response_profile: str = "teaching",
    ) -> Dict[str, Any]:
        """执行完整五段式管线.

        返回包含所有中间结果和最终产出的字典。
        任何阶段的异常都不会中断管线，而是降级处理。
        """
        timing: Dict[str, float] = {}
        total_start = time.perf_counter()

        current_stage = getattr(state, "current_cp_id", "")
        current_software = getattr(state, "software", "")
        chat_summary = getattr(state, "session_summary", "")
        response_profile = normalize_response_profile(response_profile)

        # 1+2. Query Understanding + Expansion（合并为单一阶段，减少串行调用开销）
        t0 = time.perf_counter()
        understanding, expansion = self.understand_and_expand(
            user_text, current_stage, current_software, chat_summary
        )
        timing["understand_and_expand_ms"] = int((time.perf_counter() - t0) * 1000)

        # ✅ 概念问答快速通道
        # 对于概念解释类问题，跳过复杂的 RAG 检索，直接调用 LLM
        # （expansion 已在 understand_and_expand 中产出，概念路径不使用，开销可忽略）
        if understanding.user_intent == "concept_explain":
            t_fast = time.perf_counter()
            # 只检索术语库
            glossary_entry = None
            try:
                if hasattr(self.retrieval_optimizer, 'glossary'):
                    matched = self.retrieval_optimizer._match_glossary(
                        user_text, user_text, []
                    )
                    if matched:
                        glossary_entry = matched[0]
            except Exception:
                pass

            # 直接调用 LLM 概念问答
            if self.llm and getattr(self.llm, 'enabled', False):
                try:
                    answer_text = self.llm.concept_answer(
                        user_text,
                        glossary_entry=glossary_entry,
                        software=understanding.detected_software,
                        extra_context="",
                        response_profile=response_profile,
                    )
                    timing["concept_fast_ms"] = int((time.perf_counter() - t_fast) * 1000)
                    timing["total_ms"] = timing["concept_fast_ms"] + timing["understand_and_expand_ms"]

                    return {
                        "understanding": understanding,
                        "expansion": QueryExpansion(source="fast_concept"),
                        "retrieval": RetrievalResult(glossary_entries=[glossary_entry] if glossary_entry else []),
                        "reasoning": SOPReasoning(source="fast_concept"),
                        "answer": ComposedAnswer(
                            formatted_markdown=answer_text,
                            current_judgment="概念解释",
                            source="fast_concept",
                        ),
                        "enhanced_context": f"smart_qa_intent=concept_explain\nsmart_qa_fast_path=true",
                        "structured_cards": {"type": "concept", "text": answer_text},
                        "timing_ms": timing,
                        "smart_qa_enabled": True,
                        "fast_concept_path": True,
                        "response_profile": response_profile,
                    }
                except Exception:
                    pass  # 降级到完整流程

            # 降级：如果 LLM 失败，返回术语库卡片
            if glossary_entry:
                glossary_text = f"## {glossary_entry.get('term', '概念')}\n\n{glossary_entry.get('definition_cn', '')}"
                timing["concept_fast_ms"] = int((time.perf_counter() - t_fast) * 1000)
                timing["total_ms"] = timing["concept_fast_ms"] + timing["understand_and_expand_ms"]

                return {
                    "understanding": understanding,
                    "expansion": QueryExpansion(source="glossary_only"),
                    "retrieval": RetrievalResult(glossary_entries=[glossary_entry]),
                    "reasoning": SOPReasoning(source="glossary_only"),
                    "answer": ComposedAnswer(
                        formatted_markdown=glossary_text,
                        current_judgment="术语库条目",
                        source="glossary_only",
                    ),
                    "enhanced_context": f"smart_qa_intent=concept_explain\nsmart_qa_glossary_only=true",
                    "structured_cards": {"type": "glossary", "text": glossary_text},
                    "timing_ms": timing,
                    "smart_qa_enabled": True,
                    "fast_concept_path": True,
                    "response_profile": response_profile,
                }
        # 概念问答快速通道结束，其他意图继续走完整流程

        # （expansion 已在上方 understand_and_expand 中产出，此处直接进入检索）

        # 3. RAG Retrieval
        t0 = time.perf_counter()
        try:
            retrieval = self.retrieval_optimizer.retrieve(understanding, expansion)
        except Exception:
            retrieval = RetrievalResult()
        timing["retrieve_ms"] = int((time.perf_counter() - t0) * 1000)

        # 4. SOP Reasoning
        t0 = time.perf_counter()
        try:
            reasoning = self.reasoning_agent.reason(
                understanding, expansion, retrieval, current_software
            )
        except Exception:
            reasoning = SOPReasoning(source="rule")
        timing["reason_ms"] = int((time.perf_counter() - t0) * 1000)

        # 5. Answer Composition
        t0 = time.perf_counter()
        try:
            answer = self.composer.compose(
                understanding,
                reasoning,
                retrieval,
                current_software,
                response_profile=response_profile,
            )
        except Exception:
            answer = ComposedAnswer(
                current_judgment="智能问答管线处理异常，已降级为基础模式。",
                source="rule",
            )
            answer.formatted_markdown = answer.current_judgment
        timing["compose_ms"] = int((time.perf_counter() - t0) * 1000)

        timing["total_ms"] = int((time.perf_counter() - total_start) * 1000)

        # 构建增强上下文（注入到 _polish_reply）
        enhanced_context = self._build_enhanced_context(
            understanding, expansion, retrieval, reasoning
        )

        return {
            "understanding": understanding,
            "expansion": expansion,
            "retrieval": retrieval,
            "reasoning": reasoning,
            "answer": answer,
            "enhanced_context": enhanced_context,
            "structured_cards": answer.structured_json,
            "timing_ms": timing,
            "smart_qa_enabled": True,
            "response_profile": response_profile,
        }

    def _build_enhanced_context(
        self,
        understanding: QueryUnderstanding,
        expansion: QueryExpansion,
        retrieval: RetrievalResult,
        reasoning: SOPReasoning,
    ) -> str:
        """构建增强上下文字符串，注入到 _polish_reply 的 context 参数中."""
        parts: List[str] = []
        parts.append(f"smart_qa_intent={understanding.user_intent}")
        parts.append(f"smart_qa_stage={understanding.detected_stage}")
        parts.append(f"smart_qa_software={understanding.detected_software}")
        parts.append(f"smart_qa_confidence={understanding.confidence:.2f}")
        parts.append(f"smart_qa_problem_type={understanding.problem_type}")

        if reasoning.stage_judgment:
            parts.append(f"smart_qa_judgment={reasoning.stage_judgment}")
        if reasoning.problem_analysis:
            parts.append(f"smart_qa_analysis={reasoning.problem_analysis[:200]}")
        if reasoning.qc_judgment:
            parts.append(f"smart_qa_qc={reasoning.qc_judgment[:200]}")
        if reasoning.recommended_params:
            params_str = "; ".join(
                f"{p.get('param','')}={p.get('value','')}" for p in reasoning.recommended_params[:3]
            )
            parts.append(f"smart_qa_params={params_str}")
        if reasoning.risk_warnings:
            parts.append(f"smart_qa_risks={' | '.join(reasoning.risk_warnings[:2])}")
        if understanding.should_ask_clarification:
            parts.append(f"smart_qa_needs_clarification={' | '.join(understanding.clarification_questions)}")

        return "\n".join(parts)

    # 意图中文标签（供「智能问答理解」块展示，便于 LLM 与用户侧理解）
    _INTENT_LABELS = {
        "parameter_advice": "参数咨询",
        "fault_troubleshoot": "故障排查",
        "operation_guide": "操作指导",
        "concept_explain": "概念解释",
        "decision_advice": "决策建议",
    }

    def format_understanding_block(self, understanding: "QueryUnderstanding") -> str:
        """生成注入到 LLM rewrite 上下文的【智能问答理解】块.

        该块带固定 marker「【智能问答理解】」，llm_agent._rewrite_prompt 会据此
        指示 LLM 优先使用此理解直接回应用户的实际问题（意图/阶段/软件/具体诉求），
        而非只复述关键词匹配得到的规则层模板。

        返回空串时调用方不应注入。
        """
        if understanding is None:
            return ""
        intent_label = self._INTENT_LABELS.get(understanding.user_intent, "智能问答")
        sw = {"cryosparc": "cryoSPARC", "relion": "RELION"}.get(
            (understanding.detected_software or "").strip(), "未指定"
        )
        stage_name = understanding.detected_stage_name or understanding.detected_stage or "当前阶段"
        params = (
            "、".join(understanding.mentioned_parameters)
            if understanding.mentioned_parameters
            else "（未具体指定）"
        )
        problem = understanding.problem_type or "（无）"
        conf = (
            f"{understanding.confidence:.2f}"
            if isinstance(understanding.confidence, (int, float))
            else "0.00"
        )
        summary = (
            f"用户当前在【{stage_name}】阶段、使用【{sw}】体系，"
            f"意图是【{intent_label}】，关注参数：{params}；问题类型：{problem}。"
        )
        lines = [
            "【智能问答理解】",
            f"- 用户意图：{intent_label}（{understanding.user_intent}）",
            f"- 识别阶段：{stage_name}（{understanding.detected_stage or '当前'}）",
            f"- 软件体系：{sw}",
            f"- 置信度：{conf}",
            f"- 提到参数：{params}",
            f"- 问题类型：{problem}",
            f"- 理解摘要：{summary}",
            "→ 请优先依据上述【智能问答理解】直接回应用户的实际问题"
            "（意图/阶段/软件/具体诉求）；可在不改变权威规则层事实"
            "（步骤、参数、质控结论）的前提下，补充针对性建议与下一步。",
        ]
        return "\n".join(lines)

    def should_enhance(self, state: "PipelineState") -> bool:
        """判断是否应该对当前输入启用智能问答增强.

        对于 progress / report 等本地操作，跳过智能问答管线。
        """
        action_tag = getattr(state, "action_tag", "")
        if action_tag in ("progress", "report", "advance"):
            return False
        return True

    # ---------------------------------------------------------------------------
    # 概念问答：术语库匹配 + LLM 自有知识兜底
    # ---------------------------------------------------------------------------

    def answer_concept(
        self,
        user_text: str,
        state: "PipelineState",
        response_profile: str = "teaching",
    ) -> str:
        """概念解释：返回术语卡 Markdown.

        规则模式（无 API Key）：从 glossary 匹配（含缩写扩展），
            命中→术语卡；未命中→通用提示卡（建议启用 AI 模式）。
         AI 模式（有 Key）：
            ① 检索 RAG 知识库（官方文档 + 术语 + SOP）作为增强上下文；
            ② 调用 llm.concept_answer 直接生成（1 次 LLM 调用），注入 glossary + RAG 作为权威事实；
            ③ 失败自动降级为规则术语卡（带失败原因标注）。

        该方法是概念问答的「完整产出」，不依赖 process() 五段管线，
        因此不会触发 _polish_reply 内的二次 SmartQA / RAG refs / LLM 改写，
        满足性能域「概念路径不翻倍」的硬约束。

        V4 增强：AI 模式下额外执行 RAG 检索，将官方文档/知识库条目注入 LLM prompt，
        使概念回答具备与其它问答路径同等的信息密度。
        """
        current_software = getattr(state, "software", "") or ""
        current_cp_id = getattr(state, "current_cp_id", "") or ""
        response_profile = normalize_response_profile(response_profile)

        # --- Step 1: 术语库匹配（始终执行，规则/AI 共用）---
        acronym_terms: List[str] = []
        if hasattr(self.expansion_agent, "_compute_acronym_terms"):
            try:
                acronym_terms = self.expansion_agent._compute_acronym_terms(user_text)
            except Exception:
                acronym_terms = []
        glossary_hits: List[Dict[str, Any]] = []
        if hasattr(self.retrieval_optimizer, "_match_glossary"):
            try:
                glossary_hits = self.retrieval_optimizer._match_glossary(
                    user_text, raw_user_text=user_text, acronym_terms=acronym_terms
                )
            except Exception:
                glossary_hits = []
        top_entry = glossary_hits[0] if glossary_hits else None

        # --- Step 2: AI 模式（有 Key 时走 LLM 直答 + RAG 增强上下文）---
        if self.llm is not None and getattr(self.llm, "enabled", False):
            # 2a. RAG 增强上下文：检索官方文档和知识库相关条目
            rag_context_parts: List[str] = []
            try:
                # retriever 实际挂在 retrieval_optimizer 上，需安全解析
                rag = getattr(getattr(self, "retrieval_optimizer", None), "retriever", None)
                if rag:
                    # 用扩展关键词检索（含缩写全称）
                    search_queries = [user_text]
                    if acronym_terms:
                        search_queries.append(" ".join(acronym_terms[:5]))
                    for sq in search_queries[:2]:
                        try:
                            docs = rag.search(sq, top_k=4)
                            for doc_id, text, score in docs:
                                if score >= 0.25:
                                    snippet = (text or "")[:300]
                                    rag_context_parts.append(
                                        f"[{doc_id}] (score={score:.2f}) {snippet}"
                                    )
                        except Exception:
                            pass
                    # 也取当前步骤的 SOP 片段作为补充
                    if current_cp_id:
                        sop_snippet = self._get_stage_sop(
                            current_cp_id, current_software
                        )
                        if sop_snippet:
                            rag_context_parts.append(f"[当前步骤SOP] {sop_snippet[:400]}")
            except Exception:
                pass  # RAG 检索失败不阻断主路径

            rag_references = "\n\n".join(rag_context_parts) if rag_context_parts else ""

            # 2b. 调用 LLM（注入 glossary + RAG 上下文）
            try:
                ai_text = self.llm.concept_answer(
                    user_text, top_entry, current_software,
                    extra_context=rag_references,
                    response_profile=response_profile,
                )
                if ai_text and ai_text.strip():
                    card = self._wrap_concept_card(ai_text, top_entry, ai_mode=True)
                    # 将 RAG 来源附加到卡片末尾（供 UI 展示参考来源）
                    if rag_context_parts:
                        card += (
                            "\n\n> **参考来源（RAG 增强）**："
                            + "，".join(
                                f"{d.split(']')[0].lstrip('[')}" 
                                for d in rag_context_parts[:4]
                            )
                        )
                    return card
                else:
                    # LLM 返回空但没抛异常 → 记录到 trace
                    pass
            except Exception as exc:
                # LLM 调用异常：记录原因，继续降级
                _concept_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                pass

        # --- Step 3: 规则模式 / AI 失败降级 ---
        fallback = self._rule_concept_card(user_text, top_entry, acronym_terms, current_software)
        # 如果是因 AI 失败而降级，在卡片底部注明原因
        if '_concept_error' in dir() and '_concept_error' in locals():  # noqa: F821
            fallback += f"\n\n> ⚠️ AI 模式调用失败（{_concept_error}），已降级为规则术语卡。请检查网络或 API 配置。"
        return fallback

    def _wrap_concept_card(self, ai_text: str, entry: Optional[Dict[str, Any]], ai_mode: bool = True) -> str:
        """把 LLM 生成的解释包成 Markdown 文本（不再使用 JSON，直接返回纯文本）."""
        term_label = (entry or {}).get("term", "") if entry else ""

        # 构建卡片内容
        content_parts: List[str] = [ai_text.strip()]

        if entry:
            extras: List[str] = []
            if entry.get("aliases"):
                extras.append(f"**别名**：{', '.join(entry['aliases'])}")
            if entry.get("related_file_formats"):
                extras.append(f"**相关文件格式**：{', '.join(entry['related_file_formats'])}")
            if entry.get("stage_ids"):
                extras.append(f"**关联步骤**：{', '.join(entry['stage_ids'])}")
            if entry.get("software") and entry.get("software") != "both":
                extras.append(f"**适用软件**：{entry['software']}")
            if extras:
                content_parts.append("\n".join(extras))
            content_parts.append(
                "> 来源：术语库（{0}）+ LLM 专业知识".format(
                    "已收录" if entry.get("runtime_allowed") else "草稿"
                )
            )
        else:
            content_parts.append("> 来源：LLM 专业知识（术语库未收录该词条，建议核对官方文档）")

        # 直接返回 Markdown 文本，不再包装成 JSON
        return "\n\n".join(content_parts)

    def _rule_concept_card(
        self,
        user_text: str,
        entry: Optional[Dict[str, Any]],
        acronym_terms: List[str],
        software: str,
    ) -> str:
        """规则模式术语卡（零 LLM / 零 embedding），返回纯 Markdown 文本."""
        content_parts: List[str] = []
        term_label = ""

        if entry:
            term_label = entry.get("term", "")
            # 添加标题
            content_parts.append(f"## {term_label}")
            content_parts.append(entry.get("definition_cn", ""))

            extras: List[str] = []
            if entry.get("aliases"):
                extras.append(f"**别名**：{', '.join(entry['aliases'])}")
            if entry.get("related_file_formats"):
                extras.append(f"**相关文件格式**：{', '.join(entry['related_file_formats'])}")
            if entry.get("stage_ids"):
                extras.append(f"**关联步骤**：{', '.join(entry['stage_ids'])}")
            if entry.get("software") and entry.get("software") != "both":
                extras.append(f"**适用软件**：{entry['software']}")
            if extras:
                content_parts.append("\n".join(extras))
            content_parts.append("> 来源：术语库（规则模式，未启用 LLM，答案基于本地知识库）")
        else:
            term_display = (user_text or "").strip()
            content_parts.append(f"## 概念解释")
            content_parts.append(f"当前**术语库（规则模式）尚未收录**你提到的术语（{term_display}）。")
            content_parts.append("**你可以：**")
            suggestions = ["- 在「设置」中填写 API Key 启用 AI 模式，我将基于专业 cryo-EM 知识直接解释；"]
            if acronym_terms:
                suggestions.append(f"- 已识别缩写全称：{', '.join(acronym_terms)}（仅作提示，仍需 AI 模式给出权威解释）；")
            suggestions.append("- 或检查术语拼写，常见如 EER / CTF / MRC / STAR / FSC 等。")
            content_parts.append("\n".join(suggestions))

        # 直接返回 Markdown 文本
        return "\n\n".join(content_parts)
