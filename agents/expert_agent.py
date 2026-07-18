"""Expert Agent.

Responsible for deep domain explanation, parameter interpretation and
troubleshooting guidance.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from graph.state import PipelineState
from knowledge_base.paths import load_json_with_fallback
from validator.validator import extract_params_from_text

# Performance: cached JSON loader
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


def _cached_load(knowledge_dir: str, name: str, legacy_name: Optional[str] = None, default: Any = None) -> Any:
    if _HAS_ST:
        from utils.perf_cache import cached_load_json
        return cached_load_json(name, legacy_name or "", default if default is not None else [])
    return load_json_with_fallback(knowledge_dir, name, legacy_name, default=default)


class ExpertAgent:
    def __init__(self, knowledge_dir: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.knowledge_dir = knowledge_dir or os.path.join(base, "knowledge_base")
        # Performance: use cached JSON loading
        self.rules = _cached_load(self.knowledge_dir, "rules/tier2_rules.json", "tier2_rules.json")
        self.qa_db = self._load_qa_db()

    def _load_json(self, name: str, legacy_name: Optional[str] = None):
        return load_json_with_fallback(self.knowledge_dir, name, legacy_name, default=[])

    def _load_qa_db(self) -> List[Dict]:
        """Load formal_answers.jsonl for semantic QA matching."""
        qa_path = os.path.join(self.knowledge_dir, "qa", "formal_answers.jsonl")
        if not os.path.exists(qa_path):
            return []
        try:
            with open(qa_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            result = []
            for line in lines:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    if isinstance(data, dict) and data.get("runtime_allowed", True):
                        result.append(data)
            return result
        except Exception:
            return []

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for semantic matching."""
        text = (text or "").lower()
        tokens = re.findall(r"[a-z0-9_./+-]{2,}", text)
        for term in (
            "导入", "运动", "校正", "ctf", "挑选", "二维", "三维", "分类",
            "精修", "抛光", "后处理", "分辨率", "像素", "剂量", "路径", "报错",
            "参数", "设置", "怎么", "如何", "为什么", "影响", "含义", "解释",
            "particle", "micrograph", "movie", "relion", "star", "pixel", "motion",
            "polish", "refine", "classification", "reconstruction", "box",
            "建模", "模型", "原子模型", "主链", "低分辨率", "分辨率不够",
            "cα", "ca", "trace", "modelangelo", "coot", "phenix", "handedness",
        ):
            if term in text:
                tokens.append(term)
        return tokens

    def _score_qa_match(self, user_text: str, qa: Dict, current_cp_id: str) -> float:
        """Score QA match with intent-aware weighting."""
        score = 0.0
        lowered = user_text.lower()
        qa_question = qa.get("question", "").lower()
        qa_answer = qa.get("answer", "").lower()
        qa_text = qa_question + " " + qa_answer
        
        user_tokens = set(self._tokenize(user_text))
        qa_question_tokens = set(self._tokenize(qa_question))
        qa_tokens = set(self._tokenize(qa_text))
        
        # Token overlap
        overlap = user_tokens & qa_tokens
        if overlap:
            score += len(overlap) / max(len(user_tokens), 1) * 0.3

        question_overlap = user_tokens & qa_question_tokens
        if question_overlap:
            score += len(question_overlap) / max(len(user_tokens), 1) * 0.35
        
        # Stage match bonus
        if qa.get("checkpoint_id") == current_cp_id:
            score += 0.35
        
        # Intent keyword matching (设置、怎么、参数 vs 什么、为什么、原因)
        intent_keywords = {"设置", "怎么", "如何", "参数", "建议", "推荐", "多少", "合适"}
        user_intent_tokens = user_tokens & intent_keywords
        qa_intent_tokens = qa_question_tokens & intent_keywords
        if user_intent_tokens and qa_intent_tokens:
            score += 0.15
        
        # Question keyword matching (什么、为什么、原因、影响)
        user_question_tokens = user_tokens & {"什么", "为什么", "原因", "影响", "解释", "含义"}
        qa_question_words = qa_question_tokens & {"什么", "为什么", "原因", "影响", "解释", "含义"}
        if user_question_tokens and qa_question_words:
            score += 0.15
        
        # Penalty for mismatched intent
        if user_question_tokens and not qa_question_words:
            score -= 0.1
        if user_intent_tokens and not qa_intent_tokens:
            score -= 0.1

        # Same checkpoint is not enough. Strongly penalize known cp_12 subtopics
        # when the user did not ask that subtopic.
        mismatch_topics = {
            "handedness": {"handedness", "手性", "左右手", "翻转", "invert_hand"},
            "ctf": {"ctf", "defocus", "像差", "beamtilt"},
            "mask": {"mask", "掩膜"},
        }
        for topic, words in mismatch_topics.items():
            qa_has_topic = any(w in qa_text for w in words)
            user_has_topic = any(w in lowered for w in words)
            if qa_has_topic and not user_has_topic:
                score -= 0.25 if topic == "handedness" else 0.15
        
        # Boost if question keywords appear in QA question
        for token in user_tokens:
            if token in qa_question:
                score += 0.03
        
        return max(0.0, min(score, 1.0))

    def _extract_clean_answer(self, qa: Dict) -> str:
        """Extract clean answer from QA entry, removing Q:/A: prefix and metadata."""
        answer = qa.get("answer", "")
        if answer.startswith("Q:"):
            q_end = answer.find("A:")
            if q_end != -1:
                answer = answer[q_end + 2:]
        answer = answer.replace("Evidence grade:", "").replace("Risk grade:", "").replace("Sources:", "")
        answer = re.sub(r'https?://[^\s]+', '', answer)
        answer = re.sub(r'\s+', ' ', answer).strip()
        return answer

    def _find_best_qa(self, user_text: str, current_cp_id: str) -> Optional[Dict]:
        """Find best matching QA from knowledge base."""
        if not self.qa_db:
            return None
        
        scored = []
        for qa in self.qa_db:
            score = self._score_qa_match(user_text, qa, current_cp_id)
            if score >= 0.33:
                scored.append((qa, score))
        
        if not scored:
            return None
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _match_rule(self, user_text: str):
        lowered = user_text.lower()
        for rule in self.rules:
            condition = rule.get("condition", "").lower()
            if any(token in lowered for token in condition.split() if len(token) > 1):
                return rule
        return None

    def explain(self, state: PipelineState, user_text: str) -> str:
        params = extract_params_from_text(user_text)
        if params:
            state.params.update(params)

        low_res_modeling = self._answer_low_resolution_modeling(user_text, state)
        if low_res_modeling:
            return low_res_modeling

        rule = self._match_rule(user_text)
        if rule:
            steps = rule.get("decision_tree", [])
            steps_text = "\n".join(f"- {s}" for s in steps)
            return (
                f"## 决策建议：{rule.get('rule_name', '未命名规则')}\n\n"
                f"{steps_text}\n\n"
                f"参考：{rule.get('reference', '')}"
            )

        # 改动6-7：智能参数推荐 — 从state.params自动推荐相关参数
        auto_recommendations = self._get_auto_recommendations(state)
        if auto_recommendations:
            lines = ["## 💡 参数推荐（根据已知信息自动计算）", ""]
            for param_name, rec in auto_recommendations.items():
                value = rec.get("value", "")
                reason = rec.get("reason", "")
                formula = rec.get("formula", "")
                lines.append(f"**{param_name}** = `{value}`")
                if reason:
                    lines.append(f"  - {reason}")
                if formula:
                    lines.append(f"  - 计算：{formula}")
                lines.append("")
            return "\n".join(lines)

        if "pixel_size" in params:
            return (
                f"pixel size = {params['pixel_size']} A/pixel。\n"
                "这会直接影响后续 box size、CTF 与重建尺度。"
            )
        if "ctf" in user_text.lower():
            return (
                "CTF 是衬度传递函数，主要用于估计离焦、像散和分辨率上限。\n"
                "如果 CTF fit 很差，先看 micrograph 质量和参数范围。"
            )

        # V3 enhancement: semantic QA matching from knowledge base
        best_qa = self._find_best_qa(user_text, state.current_cp_id)
        if best_qa:
            answer = self._extract_clean_answer(best_qa)
            if answer:
                return answer

        return (
            f"当前阶段：{state.current_cp_id}\n"
            "你可以把参数、报错或截图描述给我，我来解释其含义与影响。"
        )

    def _get_auto_recommendations(self, state: PipelineState) -> Dict[str, Any]:
        """改动7：整合 RecommendAgent 的自动推荐逻辑。"""
        try:
            from agents.recommend_agent import RecommendAgent
            recommender = RecommendAgent()
            round_number = 1 if state.current_cp_id in ("cp_06", "cp_07") else 2
            return recommender.auto_recommend_from_state(state.params, round_number)
        except Exception:
            return {}

    def _answer_low_resolution_modeling(self, user_text: str, state: PipelineState) -> str:
        lowered = (user_text or "").lower()
        asks_modeling = any(k in lowered for k in ("建模", "模型", "model", "modelangelo", "coot", "phenix", "trace", "cα", "ca trace"))
        asks_low_resolution = any(k in lowered for k in ("分辨率不够", "低分辨率", "分辨率低", "resolution", "不够", "够吗"))
        if not (asks_modeling and asks_low_resolution):
            return ""
        return (
            "**结论**\n\n"
            "分辨率不够时不要强行搭完整原子模型；Cα trace 可以作为保守表达，但不能包装成完整 atomic model。\n\n"
            "**原因**\n\n"
            "低分辨率 map 的可解释信息有限。若局部分辨率差于约 4 Å，侧链方向、逐残基位置和精细构象通常缺少可靠密度支撑。"
            "这时模型复杂度应降级到 map 能支持的层级：Cα trace、主链路径、二级结构、同源结构 rigid-body fitting，或 domain docking。\n\n"
            "**操作步骤**\n\n"
            "1. 先看 FSC 0.143 全局分辨率和 local resolution，不要只看一个全局数字。\n"
            "2. 用 sharpened 与 unsharpened map 交叉检查，避免 sharpening 造成假细节。\n"
            "3. 若主链密度连续、α-helix / β-sheet 可稳定识别，可做 Cα trace 或 backbone-level model。\n"
            "4. 若只看得到整体轮廓，改用同源结构 rigid-body fitting 或 domain docking，并明确标注低分辨率解释。\n"
            "5. 最后再做 map-model correlation、MolProbity、Ramachandran、real-space fit 等验证。\n\n"
            "**参数解释**\n\n"
            "- 约 4 Å 是保守边界：优于这个范围才更有机会支持 backbone/部分侧链解释；差于它时不要给逐原子结论。\n"
            "- Cα trace 表示主链级别解释，不等于完整原子模型。\n"
            "- 如果局部分辨率差异很大，应按局部区域分别决定建模粒度。\n\n"
            "**常见错误**\n\n"
            "- 分辨率不够却强行搭全原子模型。\n"
            "- 把 Cα trace 写成完整 atomic model。\n"
            "- 只报全局分辨率，不检查 local resolution 和 map-model fit。\n"
            "- 忽略 handedness、pixel size、序列文件错误等会导致模型整体不匹配的问题。\n\n"
            "**证据来源**\n\n"
            "- cp_12 模型构建/验证规则。\n"
            "- 知识库记录：低分辨率（>4 Å）强行搭原子模型是常见风险，建议仅做 Cα trace 或更低粒度解释。"
        )
