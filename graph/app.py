"""StructPilot v5.1 LangGraph orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING, Tuple

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from agents.navigator_agent import NavigatorAgent
    from agents.expert_agent import ExpertAgent
    from agents.sop_agent import SOPAgent
    from agents.memory_agent import MemoryAgent
    from agents.llm_agent import LLMAgent
    from agents.plot_agent import PlotAgent
    from agents.smart_qa_engine import SmartQAEngine
from graph.state import PipelineState
from knowledge_base.retriever import KnowledgeRetriever
from response_profiles import detect_response_focus, format_response_for_profile, normalize_response_profile
from validator.validator import InputValidator

Route = Literal["expert", "sop", "memory", "fault", "plot_interp", "end", "concept", "casual"]

# Action tags that route to a downstream node which will produce the final message.
# For these, the navigator's reply is a transitional prefix (advance notice / greeting)
# that should be prepended to the downstream node's reply as a single message.
_ROUTING_TAGS = {"stage_guide_sop", "param_advice", "plot_interpretation", "concept_explain"}
_RAG_INJECTION_MIN_SCORE = 0.5
_LOCAL_ONLY_ACTIONS = {
    "progress",
    "report",
}
_PLOT_ACTIONS = {"plot_interpretation"}


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _short_snippet(text: str, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")


def _is_generic_rule_reply(reply: str) -> bool:
    text = re.sub(r"\s+", " ", reply or "").strip()
    if not text:
        return True
    generic_markers = (
        "你可以把参数、报错或截图描述给我",
        "请根据上述建议操作，完成后告诉我结果",
        "当前阶段：",
        "暂无足够信息",
        "当前信息不足",
    )
    if len(text) < 240 and any(marker in text for marker in generic_markers):
        return True
    return False


def _extract_must_keep_facts(rule_reply: str, state: PipelineState, user_text: str = "") -> Dict[str, Any]:
    text = rule_reply or ""
    facts: Dict[str, Any] = {"must_keep_facts": [], "next_step": "", "warnings": []}
    if state.current_cp_id and state.current_cp_id in text:
        facts["must_keep_facts"].append(state.current_cp_id)
    if state.software and state.software in text.lower():
        facts["must_keep_facts"].append(state.software)
    for key, value in (state.params or {}).items():
        value_text = str(value)
        if value_text and value_text in text:
            facts["must_keep_facts"].append(value_text)
    for token in re.findall(r"\b\d+(?:\.\d+)?\s*(?:kV|eV|A|Å|px|pixel|nm|um|µm|mm|GB|MB|%|颗|张)?\b", text, flags=re.I):
        token = token.strip()
        if token and token not in facts["must_keep_facts"]:
            facts["must_keep_facts"].append(token)
    user_fact_text = user_text or ""
    for token in re.findall(r"\b\d+(?:\.\d+)?\s*(?:kV|eV|A|Å|A2|px|pix|pixel|nm|um|µm|mm|GB|MB|%|颗|张)?\b", user_fact_text, flags=re.I):
        token = token.strip()
        if token and token not in facts["must_keep_facts"]:
            facts["must_keep_facts"].append(token)
    for token in re.findall(r"\b(?:RELION|cryoSPARC|CTF|STAR|star|drift|motion|defocus|pixel|dose|2D|3D|box|particles?\.star|memory)\b", user_fact_text, flags=re.I):
        token = token.strip()
        if token and token not in facts["must_keep_facts"]:
            facts["must_keep_facts"].append(token)
    if "内存" in user_fact_text and "内存" not in facts["must_keep_facts"]:
        facts["must_keep_facts"].append("内存")
    for line in text.splitlines():
        clean = line.strip(" #-\t")
        if not clean:
            continue
        if not facts["next_step"]:
            facts["next_step"] = clean[:120]
        if any(word in clean for word in ("不要", "避免", "警告", "失败", "报错", "风险")):
            facts["warnings"].append(clean[:120])
    facts["must_keep_facts"] = facts["must_keep_facts"][:12]
    facts["warnings"] = facts["warnings"][:5]
    return facts


def _guard_llm_reply(rule_reply: str, llm_reply: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """Guard mechanism with semantic matching and intelligent fallback."""
    must_keep = [str(item).strip() for item in facts.get("must_keep_facts", []) if str(item).strip()]
    
    llm_tokens = _tokenize_for_match(llm_reply)
    llm_lower = (llm_reply or "").lower()
    
    missing = []
    for fact in must_keep:
        fact_lower = fact.lower()
        
        # Direct string match
        if fact_lower in llm_lower:
            continue
        
        # Semantic token match (e.g., "运动校正" matches "cp_02")
        fact_tokens = _tokenize_for_match(fact)
        if fact_tokens & llm_tokens:
            continue
        
        # Skip short non-numeric facts
        if len(fact) <= 3 and not fact.isdigit():
            continue
        
        # For cp_xx stage IDs, check if related Chinese terms exist
        if re.match(r"^cp_\d+$", fact):
            cp_related = any(t in llm_tokens for t in ["运动", "校正", "ctf", "挑选", "分类", "精修", "导入", "提取"])
            if cp_related:
                continue
        
        missing.append(fact)
    
    # Only critical missing facts trigger fallback
    critical_missing = [f for f in missing if len(f) > 3 or f.isdigit()]
    
    return {
        "passed": not critical_missing,
        "missing_facts": missing,
        "critical_missing": critical_missing,
        "checked_facts": must_keep,
        "fallback_to_rule": bool(critical_missing),
    }


def _tokenize_for_match(text: str) -> set:
    """Tokenize text for semantic matching."""
    text = (text or "").lower()
    tokens = set(re.findall(r"[a-z0-9_./+-]{2,}", text))
    for term in (
        "导入", "运动", "校正", "ctf", "挑选", "二维", "三维", "分类",
        "精修", "抛光", "后处理", "分辨率", "像素", "剂量", "路径", "报错",
        "参数", "设置", "怎么", "如何", "为什么", "影响", "含义", "解释",
        "relion", "cryosparc", "defocus", "motion", "particle", "micrograph",
        "memory", "内存",
    ):
        if term in text:
            tokens.add(term)
    return tokens


def _mode_label(llm_enabled: bool, refs_used: bool, images: bool) -> str:
    labels = []
    labels.append("RAG增强" if refs_used else "规则模式")
    if llm_enabled:
        labels.append("LLM改写")
    if images:
        labels.append("视觉模型已启用")
    return " / ".join(labels)


def _append_evidence_summary(answer: str, trace: Dict[str, Any]) -> str:
    """Append a concise evidence ledger to each generated answer."""
    if not answer:
        return answer
    evidence: List[str] = []
    citations = trace.get("citations") or []
    if citations:
        evidence.append(
            "RAG/knowledge sources: "
            + "; ".join(f"{c.get('ref')} {c.get('doc_id')} score={c.get('score')}" for c in citations[:4])
        )
    facts = (trace.get("rule_layer_json") or {}).get("must_keep_facts") or []
    if facts:
        evidence.append("Rule facts kept: " + ", ".join(str(x) for x in facts[:8]))
    if trace.get("images_attached"):
        evidence.append(
            f"User image evidence: {trace.get('image_count', 0)} image(s); OCR/vision is advisory for critical parameters"
        )
    if trace.get("fallback"):
        evidence.append(f"Uncertainty/fallback: {trace.get('fallback_reason') or 'rule_fallback'}")
    elif trace.get("llm_provider") or trace.get("llm_model"):
        evidence.append("LLM inference: enabled, constrained by rule/RAG evidence")
    if not evidence:
        evidence.append("No direct source evidence was attached; this answer is uncertain until checked against screenshots, logs, or official documentation")
    return answer + "\n\n---\n\n**证据与不确定性 / Evidence and uncertainty**\n" + "\n".join(f"- {item}" for item in evidence)


@dataclass
class StructPilotApp:
    navigator: "NavigatorAgent" = field(default_factory=lambda: __import__('agents.navigator_agent', fromlist=['NavigatorAgent']).NavigatorAgent())
    expert: "ExpertAgent" = field(default_factory=lambda: __import__('agents.expert_agent', fromlist=['ExpertAgent']).ExpertAgent())
    sop: "SOPAgent" = field(default_factory=lambda: __import__('agents.sop_agent', fromlist=['SOPAgent']).SOPAgent())
    memory: "MemoryAgent" = field(default_factory=lambda: __import__('agents.memory_agent', fromlist=['MemoryAgent']).MemoryAgent())
    llm: "LLMAgent" = field(default_factory=lambda: __import__('agents.llm_agent', fromlist=['LLMAgent']).LLMAgent())
    validator: InputValidator = field(default_factory=InputValidator)

    def __post_init__(self) -> None:
        self.retriever = KnowledgeRetriever(self.llm)
        self.plot_agent = __import__('agents.plot_agent', fromlist=['PlotAgent']).PlotAgent()
        self.smart_qa_engine = __import__(
            'agents.smart_qa_engine', fromlist=['SmartQAEngine']
        ).SmartQAEngine(
            llm=self.llm, retriever=self.retriever, navigator=self.navigator
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(PipelineState)
        graph.add_node("navigator", self._navigator_node)
        graph.add_node("expert", self._expert_node)
        graph.add_node("sop", self._sop_node)
        graph.add_node("memory", self._memory_node)
        graph.add_node("fault", self._fault_node)
        graph.add_node("plot_interp", self._plot_interp_node)
        graph.add_node("concept", self._concept_node)
        graph.add_node("casual", self._casual_node)
        graph.set_entry_point("navigator")
        graph.add_conditional_edges("navigator", self._route_from_navigator, {
            "expert": "expert",
            "sop": "sop",
            "memory": "memory",
            "fault": "fault",
            "plot_interp": "plot_interp",
            "concept": "concept",
            "casual": "casual",
            "end": END,
        })
        graph.add_edge("expert", "memory")
        graph.add_edge("sop", "memory")
        graph.add_edge("fault", "memory")
        graph.add_edge("plot_interp", "memory")
        graph.add_edge("concept", "memory")
        graph.add_edge("casual", "memory")
        graph.add_edge("memory", END)
        return graph.compile()

    def _route_from_navigator(self, state: PipelineState) -> Route:
        tag = state.action_tag
        if tag == "concept_explain":
            return "concept"
        if tag == "casual":
            return "casual"
        if tag == "param_advice":
            return "expert"
        if tag == "stage_guide_sop":
            return "sop"
        if tag == "stage_guide":
            return "memory"
        if tag == "fault_diagnosis":
            return "fault"
        if tag == "plot_interpretation":
            return "plot_interp"
        return "memory"

    def _filter_retrieved(self, state: PipelineState, retrieved: List[Tuple[str, str, float]]) -> List[Tuple[str, str, float]]:
        if not retrieved:
            return []
        cp = (state.current_cp_id or "").lower()
        software = (state.software or "").lower()
        preferred: List[Tuple[str, str, float]] = []
        accepted: List[Tuple[str, str, float]] = []
        for doc_id, text, score in retrieved:
            haystack = f"{doc_id}\n{text}".lower()
            if score < _RAG_INJECTION_MIN_SCORE:
                continue
            if (cp and cp in haystack) or (software and software in haystack):
                preferred.append((doc_id, text, score))
            else:
                accepted.append((doc_id, text, score))
        return (preferred + accepted)[:3]

    def _build_context(self, state: PipelineState) -> str:
        obs = state.image_observations[-3:] if getattr(state, "image_observations", None) else []
        obs_text = "; ".join(_short_snippet(str(item), 180) for item in obs)

        # 优化：注入最近 5 轮对话历史（10 条消息），增强上下文连贯性
        # 每条消息保留 200 字符（原100字符太短），确保关键信息不丢失
        history_parts: List[str] = []
        recent_msgs = (state.messages or [])[-10:]  # 从6条增加到10条
        for m in recent_msgs:
            role_label = "用户" if m.role == "user" else "助手"
            # 增加字符限制从100到200，保留更多上下文
            history_parts.append(f"{role_label}: {_short_snippet(m.content, 200)}")
        history_text = " | ".join(history_parts)

        return (
            f"current_cp={state.current_cp_id}; action={state.action_tag}; software={state.software}; "
            f"params={state.params}; session_summary={getattr(state, 'session_summary', '')}; "
            f"image_observations={obs_text}; "
            f"recent_history=[{history_text}]"
        )

    def _update_session_summary(self, state: PipelineState, user_text: str, reply: str) -> None:
        """更新会话摘要，用于跨轮对话的上下文连贯性"""
        parts = [
            f"软件: {state.software}; 当前站点: {state.current_cp_id} {state.current_cp_name}".strip(),
            f"进度: 完成{len(state.completed)} / 失败{len(state.failed)} / 跳过{len(state.skipped)}",
        ]
        if state.params:
            compact_params = ", ".join(f"{k}={v}" for k, v in list(state.params.items())[:8])
            parts.append(f"关键参数: {compact_params}")
        if state.failed:
            parts.append(f"失败点: {', '.join(state.failed[-5:])}")
        if state.image_observations:
            latest_obs = state.image_observations[-1]
            parts.append(f"最新图片证据: {_short_snippet(str(latest_obs), 220)}")

        # 优化：增加最近3轮对话的关键信息摘要，提升上下文连贯性
        recent_topics = []
        if len(state.messages) >= 2:
            # 提取最近3轮对话的关键词（动作标签 + 内容片段）
            for msg in state.messages[-6:]:
                if msg.role == "user":
                    action = getattr(msg, "action_tag", "") or ""
                    snippet = _short_snippet(msg.content, 60)
                    if action and action != "casual":
                        recent_topics.append(f"{action}:{snippet}")
                    else:
                        recent_topics.append(snippet)

        if recent_topics:
            parts.append(f"近期讨论: {' → '.join(recent_topics[-3:])}")

        if user_text:
            parts.append(f"当前问题: {_short_snippet(user_text, 180)}")
        if reply:
            parts.append(f"当前答复要点: {_short_snippet(reply, 220)}")

        state.session_summary = "\n".join(parts)[:1500]  # 从1200增加到1500字符

    def _polish_reply(self, state: PipelineState, reply: str) -> str:
        response_profile = normalize_response_profile(getattr(state, "response_profile", "teaching"))
        # 概念解释由 SmartQAEngine.answer_concept 完整生成（规则模式术语卡 / AI 模式 LLM 直答 + RAG 增强）。
        # 早退以避免重复工作与「参考来源」噪音：跳过 SmartQA 二次管线、RAG refs 检索、LLM 改写。
        # V4: answer_concept 内部已自行执行 RAG 检索 + LLM 调用，此处仅记录诊断信息到 trace。
        if state.action_tag == "concept_explain":
            state.smart_qa_cards = getattr(state, "smart_qa_cards", {}) or {}
            # 从 reply 内容推断实际走的是 AI 还是规则模式
            is_ai_mode = bool(reply and ("LLM 专业知识" in reply or "参考来源（RAG" in reply))
            is_rule_mode = bool(reply and ("规则模式" in reply or "尚未收录" in reply))
            state.last_qa_trace = {
                "mode_label": f"概念解释（{'AI+RAG' if is_ai_mode else '规则' if is_rule_mode else '未知'}）",
                "concept": True,
                "skipped_polish": True,
                "llm_enabled": bool(getattr(self.llm, "enabled", False)),
                "ai_mode_detected": is_ai_mode,
                "rule_mode_detected": is_rule_mode,
                "reply_length": len(reply),
                "response_profile": response_profile,
                "response_focus": detect_response_focus(state.user_input or "", state.action_tag),
            }
            return format_response_for_profile(reply, response_profile)
        total_start = time.perf_counter()
        trace: Dict[str, Any] = {
            "llm_enabled": bool(getattr(self.llm, "enabled", False)),
            "embedding_enabled": bool(getattr(self.llm, "embedding_enabled", False)),
            "images_attached": bool(state.pending_images),
            "image_count": len(state.pending_images),
            "image_observations_count": len(getattr(state, "image_observations", []) or []),
            "retrieved_docs": [],
            "citations": [],
            "timings_ms": {},
            "fallback": False,
            "fallback_reason": "",
            "guard": {},
            "mode_label": "规则模式",
            "response_profile": response_profile,
        }
        context = self._build_context(state)
        response_focus = detect_response_focus(state.user_input or "", state.action_tag, context)
        trace["response_focus"] = response_focus

        # --- Smart QA Engine: 智能问答管线增强 ---
        smart_qa_result: Dict[str, Any] = {}
        smart_qa_cards: Dict[str, Any] = {}
        smart_qa_timing: Dict[str, int] = {}
        smart_qa_reasoning_md: str = ""  # 缓存 SmartQA 推理结果，待 references 拼装后注入
        smart_qa_answer_md: str = ""
        try:
            if self.smart_qa_engine.should_enhance(state) and state.action_tag not in _LOCAL_ONLY_ACTIONS:
                smart_qa_result = self.smart_qa_engine.process(
                    state.user_input or "", state, response_profile=response_profile
                )
                understanding = smart_qa_result.get("understanding")
                # 将「智能问答理解」块注入到上下文：rewrite 会据此优先直接回应用户实际问题，
                # 而不是只复述 navigator/expert 关键词匹配得到的规则层模板。
                if understanding is not None:
                    sqa_block = self.smart_qa_engine.format_understanding_block(understanding)
                    if sqa_block:
                        context = f"{context}\n{sqa_block}"
                # 兼容旧字段：enhanced_context 仍作为补充证据注入
                enhanced_ctx = smart_qa_result.get("enhanced_context", "")
                if enhanced_ctx:
                    context = f"{context}\n{enhanced_ctx}"
                smart_qa_cards = smart_qa_result.get("structured_cards", {})
                smart_qa_timing = smart_qa_result.get("timing_ms", {})
                trace["smart_qa"] = {
                    "enabled": True,
                    "intent": understanding.user_intent if understanding else "",
                    "detected_stage": understanding.detected_stage if understanding else "",
                    "confidence": understanding.confidence if understanding else 0.0,
                    "source": understanding.source if understanding else "rule",
                    "timing_ms": smart_qa_timing,
                    "cards": smart_qa_cards,
                }
                # 顶层可观测字段：便于用户侧排查最终回答走的是 LLM 还是规则
                if understanding is not None:
                    trace["intent"] = understanding.user_intent
                    trace["confidence"] = understanding.confidence
                    trace["source"] = understanding.source
                # 缓存 SmartQA 推理结果，待 references 定义后追加
                sqa_answer = smart_qa_result.get("answer")
                if sqa_answer and sqa_answer.formatted_markdown:
                    if len(sqa_answer.formatted_markdown) > 50:
                        smart_qa_answer_md = sqa_answer.formatted_markdown
                        smart_qa_reasoning_md = sqa_answer.formatted_markdown
            else:
                trace["smart_qa"] = {"enabled": False, "reason": "skipped_local_action"}
        except Exception as exc:
            trace["smart_qa"] = {"enabled": False, "error": str(exc)[:200]}

        retrieval_start = time.perf_counter()
        # Performance: use cached RAG search (LRU cache with software/cp_id isolation)
        try:
            from utils.perf_cache import rag_search_cache
            retrieved = rag_search_cache(
                self.retriever,
                state.user_input or "",
                top_k=6,
                software=state.software or "",
                cp_id=state.current_cp_id or "",
            )
        except Exception:
            retrieved = self.retriever.search(state.user_input or "", top_k=6)
        filtered = self._filter_retrieved(state, retrieved)
        trace["timings_ms"]["retrieval"] = _elapsed_ms(retrieval_start)
        trace["retrieved_docs"] = [
            {"doc_id": doc_id, "score": round(score, 3), "snippet": _short_snippet(text)}
            for doc_id, text, score in retrieved
        ]
        trace["citations"] = [
            {"ref": f"R{i}", "doc_id": doc_id, "score": round(score, 3)}
            for i, (doc_id, _text, score) in enumerate(filtered, start=1)
        ]

        references = "\n\n".join(
            f"[R{i}] {doc_id} score={score:.2f}\n{text}"
            for i, (doc_id, text, score) in enumerate(filtered, start=1)
        )
        # 将 SmartQA 推理结果追加到 references（此时 references 已定义）
        if smart_qa_reasoning_md:
            references = f"{references}\n\n[SmartQA] 智能推理结果\n{smart_qa_reasoning_md}" if references else f"[SmartQA] 智能推理结果\n{smart_qa_reasoning_md}"
        image_paths = [img.get("image_path") for img in state.pending_images if img.get("image_path")]
        skip_llm = state.action_tag in _LOCAL_ONLY_ACTIONS and not image_paths
        use_smartqa_direct = (
            bool(smart_qa_answer_md)
            and not bool(getattr(self.llm, "enabled", False))
            and state.action_tag not in _LOCAL_ONLY_ACTIONS
            and _is_generic_rule_reply(reply)
        )
        facts = _extract_must_keep_facts(reply, state, state.user_input or "")
        trace["rule_layer_json"] = facts

        if use_smartqa_direct:
            polished = smart_qa_answer_md
            trace["fallback"] = True
            trace["fallback_reason"] = "smartqa_rule_direct"
            trace["timings_ms"]["llm"] = 0
        elif skip_llm:
            polished = reply
            trace["fallback"] = True
            trace["fallback_reason"] = "local_fast_path"
            trace["timings_ms"]["llm"] = 0
        else:
            llm_start = time.perf_counter()
            stream_sink = getattr(self, "_stream_sink", None)
            if stream_sink is not None and hasattr(self.llm, "rewrite_with_metadata_stream"):
                try:
                    polished = ""
                    for _chunk in self.llm.rewrite_with_metadata_stream(
                        state.user_input or "", reply, context=context,
                        image_paths=image_paths, references=references,
                        response_profile=response_profile,
                    ):
                        polished += _chunk
                        stream_sink(_chunk)
                    if not polished:
                        polished = reply
                    llm_result = {"text": polished, "fallback": False, "fallback_reason": "", "provider": "", "model": ""}
                except Exception:
                    llm_result = self.llm.rewrite_with_metadata(
                        state.user_input or "", reply, context=context,
                        image_paths=image_paths, references=references,
                        response_profile=response_profile,
                    )
                    polished = llm_result.get("text", reply)
                trace["fallback"] = bool(llm_result.get("fallback", False))
                trace["fallback_reason"] = llm_result.get("fallback_reason", "")
                trace["llm_provider"] = llm_result.get("provider", "")
                trace["llm_model"] = llm_result.get("model", "")
            elif hasattr(self.llm, "rewrite_with_metadata"):
                llm_result = self.llm.rewrite_with_metadata(
                    state.user_input or "", reply, context=context,
                    image_paths=image_paths, references=references,
                    response_profile=response_profile,
                )
                polished = llm_result.get("text", reply)
                trace["fallback"] = bool(llm_result.get("fallback", False))
                trace["fallback_reason"] = llm_result.get("fallback_reason", "")
                trace["llm_provider"] = llm_result.get("provider", "")
                trace["llm_model"] = llm_result.get("model", "")
            else:
                polished = self.llm.rewrite(
                    state.user_input or "", reply, context=context,
                    image_paths=image_paths, references=references,
                    response_profile=response_profile,
                )
            trace["timings_ms"]["llm"] = _elapsed_ms(llm_start)

        guard = _guard_llm_reply(reply, polished, facts)
        trace["guard"] = guard
        if guard.get("fallback_to_rule"):
            missing = guard.get("missing_facts", []) or []
            critical_missing = guard.get("critical_missing", []) or []
            
            # Intelligent fusion: prefer LLM output and add missing points
            if critical_missing:
                if len(reply) > 100 and len(polished) > 100:
                    polished = polished + "\n\n---\n\n**补充要点**：" + "，".join(str(item) for item in critical_missing[:8])
                    trace["fallback"] = False
                    trace["fallback_reason"] = "guard_mixed"
                else:
                    suffix = ""
                    if missing:
                        suffix = "\n\n输入要点已保留：" + "，".join(str(item) for item in missing[:12])
                    polished = reply + suffix
                    trace["fallback"] = True
                    trace["fallback_reason"] = "guard_missing_facts"
            else:
                # Non-critical missing: supplement instead of fallback
                if missing:
                    polished = polished + "\n\n**补充要点**：" + "，".join(str(item) for item in missing[:8])
                trace["fallback"] = False
                trace["fallback_reason"] = "guard_supplemented"

        if filtered:
            cite_text = "，".join(f"{c['ref']} {c['doc_id']} ({c['score']})" for c in trace["citations"])
            polished = f"{polished}\n\n参考来源：{cite_text}"

        polished = _append_evidence_summary(polished, trace)
        evidence_hint = "，".join(
            f"{item.get('ref')} {item.get('doc_id')}" for item in trace.get("citations", [])
        )
        uncertainty_hint = ""
        if not trace.get("citations") and not image_paths:
            uncertainty_hint = "本轮没有直接文档或图像证据，结论主要来自规则层，仍需用实际结果验证。"
        polished = format_response_for_profile(
            polished,
            response_profile,
            evidence_hint=evidence_hint,
            uncertainty_hint=uncertainty_hint,
        )
        trace["timings_ms"]["total"] = _elapsed_ms(total_start)
        # Merge smart_qa sub-timings into trace for performance monitoring
        if smart_qa_timing:
            for k, v in smart_qa_timing.items():
                trace["timings_ms"][f"smart_qa_{k}"] = v
        trace["mode_label"] = _mode_label(
            bool(getattr(self.llm, "enabled", False)) and not skip_llm,
            bool(filtered),
            bool(image_paths),
        )
        # Store smart_qa structured cards in state for UI consumption
        state.smart_qa_cards = smart_qa_cards or {}
        state.last_qa_trace = trace
        if image_paths:
            state.pending_images = []
        return polished

    def _record_assistant(self, state: PipelineState, content: str, action_tag: str) -> None:
        self._update_session_summary(state, state.user_input or "", content)
        response_profile = normalize_response_profile(getattr(state, "response_profile", "teaching"))
        metadata = {
            "qa_trace": getattr(state, "last_qa_trace", {}) or {},
            "response_profile": response_profile,
        }
        state.add_message("assistant", content, action_tag=action_tag, metadata=metadata)

    def _consume_prefix(self, state: PipelineState) -> str:
        """Pop the transitional prefix stored by navigator (advance notice / greeting)."""
        prefix = getattr(state, "_nav_prefix", "") or ""
        state._nav_prefix = ""
        return prefix.strip()

    def _navigator_node(self, state: PipelineState) -> PipelineState:
        reply, action = self.navigator.handle_input(state, state.user_input or "")
        state.action_tag = action
        if action in _ROUTING_TAGS or action == "casual":
            # Downstream node (sop/expert/concept/casual) will produce the final content.
            # Store the raw prefix text (greeting / advance notice) to prepend,
            # and avoid a duplicate LLM call + duplicate chat bubble.
            state._nav_prefix = reply
        else:
            state.agent_reply = self._polish_reply(state, reply)
            self._record_assistant(state, state.agent_reply, action)
        return state

    def _expert_node(self, state: PipelineState) -> PipelineState:
        reply = self.expert.explain(state, state.user_input or "")
        prefix = self._consume_prefix(state)
        if prefix:
            reply = f"{prefix}\n\n{reply}"
        state.action_tag = "param_advice"
        state.agent_reply = self._polish_reply(state, reply)
        self._record_assistant(state, state.agent_reply, "param_advice")
        return state

    def _sop_node(self, state: PipelineState) -> PipelineState:
        reply = self.sop.quick_sop(state)
        prefix = self._consume_prefix(state)
        if prefix:
            reply = f"{prefix}\n\n---\n\n{reply}"
        state.action_tag = "stage_guide"
        state.agent_reply = self._polish_reply(state, reply)
        self._record_assistant(state, state.agent_reply, "stage_guide")
        return state

    def _fault_node(self, state: PipelineState) -> PipelineState:
        result = self.validator.validate_feedback(state.user_input or "")
        reply = f"## 故障预检\n\n{result.summary}\n\n{result.suggestion}"
        state.action_tag = "fault_diagnosis"
        state.last_qc_result = result.to_dict()
        state.agent_reply = self._polish_reply(state, reply)
        self._record_assistant(state, state.agent_reply, "fault_diagnosis")
        return state

    def _plot_interp_node(self, state: PipelineState) -> PipelineState:
        user_text = state.user_input or ""
        plot_type = self.plot_agent.detect_plot_type(user_text, state.current_cp_id)
        if plot_type:
            reply = self.plot_agent.interpret(plot_type, state.current_cp_id)
        else:
            available = self.plot_agent.list_plot_types_for_cp(state.current_cp_id)
            if available:
                avail_list = "\n".join(f"- {a['name']}" for a in available)
                reply = (
                    f"## 📊 图表解读\n\n"
                    f"当前步骤（{state.current_cp_name}）可解读以下图表类型：\n\n"
                    f"{avail_list}\n\n"
                    f"请告诉我你想解读哪种图表（如「解读 FSC」），或上传结果截图并指定图表类型。"
                )
            else:
                reply = (
                    f"## 📊 图表解读\n\n"
                    f"当前步骤（{state.current_cp_name}）暂无可解读的图表类型。"
                )
        state.action_tag = "plot_interpretation"
        state.agent_reply = self._polish_reply(state, reply)
        self._record_assistant(state, state.agent_reply, "plot_interpretation")
        return state

    def _concept_node(self, state: PipelineState) -> PipelineState:
        """概念问答节点：由 SmartQAEngine.answer_concept 完整生成术语卡。

        概念答案已在 answer_concept 内产出（规则模式术语卡 / AI 模式 LLM 直答 + RAG 增强），
        因此 _polish_reply 对 concept_explain 早退，不再二次运行 SmartQA 管线、
        RAG refs 检索与 LLM 改写 —— 避免概念路径 LLM 调用翻倍与「参考来源」噪音。

        V4 增强：answer_concept 内部已自行执行 RAG 检索并注入 LLM prompt，
        trace 中记录 AI/规则模式选择与 RAG 命中数。
        """
        user_text = state.user_input or ""
        try:
            reply = self.smart_qa_engine.answer_concept(
                user_text,
                state,
                response_profile=getattr(state, "response_profile", "teaching"),
            )
        except Exception as exc:
            # 返回纯 Markdown 格式的错误信息
            reply = f"## 概念解释\n\n概念问答模块暂时不可用：{exc}\n\n你可在设置中启用 AI 模式，或检查术语库（glossary.json）。"
        if not reply:
            # 返回纯 Markdown 格式的降级信息
            reply = "## 概念解释\n\n暂时无法生成解释，请稍后再试，或在设置中启用 AI 模式。"

        # 诊断 trace：记录是否走了 AI 模式 + RAG 增强情况
        is_ai = bool(reply and "LLM 专业知识" in reply)
        has_rag_refs = bool(reply and "参考来源（RAG" in reply)

        state.action_tag = "concept_explain"
        state.agent_reply = self._polish_reply(state, reply)
        self._record_assistant(state, state.agent_reply, "concept_explain")
        return state

    def _casual_node(self, state: PipelineState) -> PipelineState:
        """双轨 Track L：闲聊/通用问题节点。

        有 Key（AI 模式）：llm.casual_reply 直接生成自然回复（1 次 LLM 调用）；
        无 Key（基础模式）：navigator.casual_rule_reply 返回友好规则回复（零网络、零 LLM）。

        刻意不进入 _polish_reply（无 RAG refs、无二次改写），保持轻量；
        casual 本身已是「LLM 直答」轨道，无需再叠加规则层增强。
        """
        user_text = state.user_input or ""
        reply = ""
        try:
            if getattr(self.llm, "enabled", False):
                reply = self.llm.casual_reply(
                    user_text,
                    response_profile=getattr(state, "response_profile", "teaching"),
                )
        except Exception:
            reply = ""
        if not reply:
            try:
                reply = self.navigator.casual_rule_reply(user_text)
            except Exception:
                reply = "（闲聊回复暂时不可用，请稍后再试。）"
        if not reply:
            reply = "（闲聊回复暂时不可用，请稍后再试。）"
        state.action_tag = "casual"
        state.agent_reply = reply
        self._record_assistant(state, state.agent_reply, "casual")
        return state

    def _memory_node(self, state: PipelineState) -> PipelineState:
        try:
            self.memory.capture_state(state)
        except Exception as exc:
            state.error = f"会话保存失败：{exc}"
            state.error_node = "memory"
        return state

    def handle(
        self,
        state: PipelineState,
        user_text: str,
        response_profile: str = "teaching",
        stream_sink=None,
    ) -> PipelineState:
        state.response_profile = normalize_response_profile(response_profile)
        self._stream_sink = stream_sink
        try:
            self.memory.ingest_user_message(state, user_text)
            result = self.graph.invoke(state)
        finally:
            self._stream_sink = None
        if isinstance(result, PipelineState):
            return result
        if isinstance(result, dict):
            for key, value in result.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            return state
        return state
