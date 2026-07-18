"""Navigator Agent with strict checkpoint state transitions."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

from graph.state import PipelineState, CheckpointStatus
from knowledge_base.paths import load_json_with_fallback
from validator.validator import InputValidator, extract_params_from_text
from version import APP_DISPLAY_NAME

# Performance: cached JSON loader (uses st.cache_data when Streamlit is available,
# falls back to direct file read in non-Streamlit contexts like tests/eval).
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


def _cached_load(knowledge_dir: str, name: str, legacy_name: Optional[str] = None, default: Any = None) -> Any:
    """Load JSON with caching. Uses st.cache_data in Streamlit context, falls
    back to load_json_with_fallback in CLI/test context."""
    if _HAS_ST:
        from utils.perf_cache import cached_load_json
        return cached_load_json(name, legacy_name or "", default if default is not None else [])
    return load_json_with_fallback(knowledge_dir, name, legacy_name, default=default)


class NavigatorAgent:
    def __init__(self, knowledge_dir: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.knowledge_dir = knowledge_dir or os.path.join(base, "knowledge_base")
        self.input_validator = InputValidator()
        # Performance: use cached JSON loading (st.cache_data in Streamlit context)
        self.checkpoints = _cached_load(self.knowledge_dir, "flows/pipeline_checkpoints.json", "pipeline_checkpoints.json")
        self.relion_stage_cards = _cached_load(self.knowledge_dir, "flows/relion_stage_cards.json", "relion_stage_cards.json")
        self.coach_templates = _cached_load(self.knowledge_dir, "coach_templates.json")
        self.faults = _cached_load(self.knowledge_dir, "faults/fault_trouble.json", "fault_trouble.json")
        self.rules = _cached_load(self.knowledge_dir, "rules/tier2_rules.json", "tier2_rules.json")
        self.official_guide = _cached_load(self.knowledge_dir, "sources/official_guide_kb.json", "official_guide_kb.json")
        self._plot_agent = None
        self._recommend_agent = None

    def _get_relion_stage_card(self, cp_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(self.relion_stage_cards, list):
            return None
        for card in self.relion_stage_cards:
            if isinstance(card, dict) and card.get("id") == cp_id:
                return card
        return None

    def _load_json(self, name: str, legacy_name: Optional[str] = None) -> Any:
        return load_json_with_fallback(self.knowledge_dir, name, legacy_name, default=[])

    def _get_cp(self, cp_id: str) -> Optional[Dict[str, Any]]:
        for cp in self.checkpoints:
            if cp.get("checkpoint_id") == cp_id:
                return cp
        return None

    def _next_cp_id(self, cp_id: str) -> Optional[str]:
        ids = [cp.get("checkpoint_id") for cp in self.checkpoints]
        if cp_id not in ids:
            return None
        idx = ids.index(cp_id)
        return ids[idx + 1] if idx + 1 < len(ids) else None

    def _sync_cp_name(self, state: PipelineState) -> None:
        cp = self._get_cp(state.current_cp_id)
        state.current_cp_name = cp.get("checkpoint_cn", "") if cp else ""

    def get_opening_speech(self) -> str:
        return self.coach_templates.get("coach_opening", {}).get(
            "template", f"你好，我是 {APP_DISPLAY_NAME} 教练。"
        )

    def _append_list(self, lines: list, title: str, items: Any) -> None:
        if not isinstance(items, list):
            return
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        if not cleaned:
            return
        lines.extend(["", f"### {title}"])
        for item in cleaned:
            lines.append(f"- {item}")

    def get_stage_guide(self, state: PipelineState, cp_id: Optional[str] = None) -> str:
        cp_id = cp_id or state.current_cp_id
        cp = self._get_cp(cp_id)
        if not cp:
            return "未找到该检查站。"
        software = state.software if state.software in ("cryosparc", "relion") else "relion"

        if software == "relion":
            relion_card = self._get_relion_stage_card(cp_id)
            if relion_card:
                return self._format_relion_guide(cp, relion_card)

        guide = cp.get(software, cp.get("cryosparc", {}))
        steps = guide.get("key_steps", [])
        checks = cp.get("qc_check", [])
        pitfalls = cp.get("common_pitfalls", [])
        coach = cp.get("coach_prompt", "")

        lines = [
            f"## 检查站 #{cp.get('order', '?')}: {cp.get('checkpoint_cn', '')}",
            "",
            f"**目标**: {cp.get('stage_goal', '')}",
            "",
        ]

        if coach:
            lines.append(f"> 💬 {coach}")
            lines.append("")

        if steps:
            lines.append("**步骤**:")
            for i, s in enumerate(steps):
                lines.append(f"{i+1}. {s}")
            lines.append("")

        if checks:
            lines.append("**QC 标准**:")
            for c in checks:
                lines.append(f"- {c}")
            lines.append("")

        if pitfalls:
            lines.append("**⚠️ 常见坑**:")
            for p in pitfalls:
                lines.append(f"- {p}")
            lines.append("")

        # 注入参数推荐
        rec_lines = self._inject_recommendations(state, cp)
        if rec_lines:
            lines.extend(rec_lines)
            lines.append("")

        # 注入决策树提示
        decision_lines = self._inject_decision_hint(cp)
        if decision_lines:
            lines.extend(decision_lines)
            lines.append("")

        # 注入官方知识引用
        guide_lines = self._inject_official_guide(cp)
        if guide_lines:
            lines.extend(guide_lines)
            lines.append("")

        return "\n".join(lines)

    def _format_relion_guide(self, cp: Dict[str, Any], card: Dict[str, Any]) -> str:
        label = str(card.get("label_cn") or card.get("name") or cp.get("checkpoint_cn", ""))
        lines = [f"## 检查站 #{cp.get('order', '?')}: {label}", ""]
        goal = str(card.get("goal") or cp.get("stage_goal", "")).strip()
        if goal:
            lines.extend(["### 目标", goal])
        self._append_list(lines, "输入", card.get("inputs"))
        self._append_list(lines, "RELION Job", card.get("relion_jobs"))
        self._append_list(lines, "关键参数", card.get("key_parameters"))
        self._append_list(lines, "QC 检查", card.get("qc_checks"))
        self._append_list(lines, "常见坑", card.get("common_pitfalls"))
        lines.extend(["", f"当前阶段: {cp.get('checkpoint_id', '')}"])
        return "\n".join(lines)

    def _mark_current(self, state: PipelineState, status: CheckpointStatus, notes: str = "") -> None:
        self._sync_cp_name(state)
        state.mark_checkpoint(state.current_cp_id, status, notes, state.user_input)

    def _skip_current(self, state: PipelineState, notes: str = "用户选择跳过") -> str:
        self._mark_current(state, "skipped", notes)
        next_id = self._next_cp_id(state.current_cp_id)
        if not next_id:
            return "## 已跳过当前检查站，且没有下一站。"
        next_cp = self._get_cp(next_id)
        state.current_cp_id = next_id
        state.current_cp_name = next_cp.get("checkpoint_cn", "") if next_cp else ""
        state.mark_checkpoint(state.current_cp_id, "in_progress", "进入下一站", state.user_input)
        return self.get_stage_guide(state, state.current_cp_id)

    # ------------------------------------------------------------------
    # 双轨路由（A 域）：简单/通用问题 vs 专业问题的判别
    # ------------------------------------------------------------------
    # cryo-EM 领域关键词：命中即视为专业问题，走 Track R（后续 param/op/fault 管线）。
    _CRYOEM_DOMAIN_HINTS = [
        "导入", "电影", "movie", "motion", "运动校正", "漂移", "drift", "ctf",
        "傅里叶", "散焦", "defocus", "拾取", "picking", "颗粒", "particle",
        "提取", "extraction", "分类", "classification", "二维", "2d", "三维", "3d",
        "重构", "refine", "精修", "锐化", "sharpen", "掩膜", "mask", "分辨率",
        "resolution", "验证", "validation", "导出", "export", "校正", "cryosparc",
        "relion", "像素", "pixel", "box", "欠焦", "电压", "voltage", "剂量",
        "dose", "放大", "magnification", "mrc", "star", "eer", "tif", "步骤",
        "怎么做", "如何", "参数", "建议", "推荐", "sop", "qc", "质控", "fsc",
        "取向", "orientation", "ab initio", "abinitio", "job", "作业", "微图",
        "micrograph", "缺陷", "对称", "symmetry", "b-factor", "bfactor",
    ]
    # 控制/导航指令：即使无领域关键词也不视为闲聊，避免吞掉「下一步/继续」等。
    _CONTROL_HINTS = [
        "开始", "从头", "跳过", "进度", "报告", "下一步", "继续", "完成",
        "重来", "重新", "帮助", "设置", "退出", "回到", "返回", "总结",
        "怎么用这个", "教程", "演示",
    ]

    def _has_domain_keyword(self, text_lower: str) -> bool:
        return any(h in text_lower for h in self._CRYOEM_DOMAIN_HINTS)

    def _is_casual_input(self, text_lower: str) -> bool:
        """双轨路由（Track L）：无 cryo-EM 领域关键词、且非控制/导航指令 → 闲聊/通用问题。

        这类问题直接交 LLM 直答（有 Key）/ 规则友好回复（无 Key），不进入工作流管线。
        含领域关键词的专业问题一律走 Track R（后续 param/op/fault 管线）。
        """
        if not text_lower.strip():
            return False
        if any(c in text_lower for c in self._CONTROL_HINTS):
            return False
        if self._has_domain_keyword(text_lower):
            return False
        return True

    def casual_rule_reply(self, user_text: str) -> str:
        """无 Key / 基础模式下的闲聊友好回复（零网络、零 LLM）。"""
        t = (user_text or "").lower()
        greetings = ["你好", "您好", "hi", "hello", "在吗", "在不在", "哈喽"]
        if any(g in t for g in greetings):
            return (
                "你好！我是 **StructPilot**，你的 cryo-EM 单颗粒分析（cryoSPARC / RELION 双体系）"
                "陪跑教练 🤝。关于冷冻电镜数据处理 14 步流程（导入、运动校正、CTF、颗粒拾取、"
                "2D/3D 分类、精修、锐化、分辨率验证等）的任意一步，直接告诉我即可～"
            )
        return (
            "我是 **StructPilot**，专注 cryo-EM 单颗粒分析的陪跑教练。你的问题似乎与流程操作无关；"
            "若想了解某一步的**原理、参数或操作**，直接问我就好。\n\n"
            "（当前为基础模式、未启用 AI，通用问答能力有限；可在「设置」中填写 API Key "
            "启用 AI 模式，让我更自由地回答通用问题。）"
        )

    def handle_input(self, state: PipelineState, user_text: str) -> Tuple[str, str]:
        state.user_input = user_text
        state.user_input_lower = user_text.lower().strip()
        state.add_message(
            "user",
            user_text,
            metadata={"response_profile": getattr(state, "response_profile", "teaching")},
        )
        params = extract_params_from_text(user_text)
        if params:
            state.params.update(params)

        if not state.session_started and any(k in state.user_input_lower for k in ["开始", "start", "从头"]):
            state.session_started = True
            state.current_cp_id = "cp_01"
            self._sync_cp_name(state)
            state.mark_checkpoint(state.current_cp_id, "in_progress", "会话开始", user_text)
            return self.get_opening_speech(), "stage_guide_sop"

        if any(k in state.user_input_lower for k in ["跳过", "skip", "暂时略过"]):
            self._mark_current(state, "skipped", "用户选择跳过")
            next_id = self._next_cp_id(state.current_cp_id)
            if not next_id:
                return "## 已跳过当前检查站，且没有下一站。", "advance"
            next_cp = self._get_cp(next_id)
            state.current_cp_id = next_id
            state.current_cp_name = next_cp.get("checkpoint_cn", "") if next_cp else ""
            state.mark_checkpoint(state.current_cp_id, "in_progress", "进入下一站", user_text)
            return f"⏭️ 已跳过当前阶段，进入下一阶段：{state.current_cp_name}。", "stage_guide_sop"

        if any(k in state.user_input_lower for k in ["进度", "progress", "到哪里了"]):
            return self.get_progress(state), "progress"
        if any(k in state.user_input_lower for k in ["报告", "总结", "report"]):
            return self.generate_report(state), "report"

        # 双轨路由（A 域）：简单/通用问题（无 cryo-EM 领域关键词、非控制指令）
        # -> Track L（casual 轨道：LLM 直答 / 无 Key 时规则友好回复），不进入工作流管线。
        if self._is_casual_input(state.user_input_lower):
            return "", "casual"

        # 图表解读类问题 -> 交给 PlotAgent（必须在 expert_triggers 之前，因为 "FSC" "怎么看" 等词也会命中 expert）
        plot_triggers = [
            "解读", "怎么读", "怎么看", "分析", "帮我看看", "帮我看",
            "fsc", "FSC", "取向", "orientation", "ess", "ESS",
            "guinier", "Guinier", "类别平均", "class average",
            "ncc", "NCC", "噪声模型", "noise model", "后验精度", "posterior",
        ]
        if any(k in state.user_input_lower for k in plot_triggers):
            return "", "plot_interpretation"

        # SOP 类问题：怎么做、步骤、操作流程 -> 交给 SOP Agent
        sop_triggers = [
            "怎么做", "如何做", "步骤", "操作", "流程", "sop", "标准流程",
            "具体步骤", "详细步骤", "教程", "指导", "指引",
        ]
        if any(k in state.user_input_lower for k in sop_triggers):
            return "", "stage_guide_sop"

        # 概念解释类问题（是什么 / 为什么重要 / 原理 / 作用 / 含义 / 定义 / 全称 / 缩写 / 文件格式 / 干嘛用）
        # -> 交给概念节点（LLM 直答 / 规则术语卡，属双轨 Track L）。
        # 必须在 expert_triggers 之前：expert_triggers 也含「是什么/含义/定义」，
        # 但概念问答需要专门的术语库匹配 + LLM 自有知识兜底，不应走 param_advice。
        # 因果/原理类（为什么…重要/原理/作用/影响）此前被 expert_triggers 的「为什么」误判为
        # param_advice，导致「为什么 pixel size 很重要」答成「Box Size 决策」（答非所问）；
        # 现统一收归 concept_explain。若同时含故障信号（差/失败/报错…）则仍留给 fault/param 处理。
        concept_intro = [
            "是什么", "是什么文件", "是什么格式", "什么含义", "什么意思",
            "怎么理解", "含义", "定义", "干嘛", "干什么用", "干嘛的",
            "全称", "缩写", "简称", "解释一下", "是什么东西", "是什么原理",
            # —— 因果 / 原理类（修复答非所问）——
            "为什么", "为何", "什么原因", "原理", "机制", "作用", "影响",
            "重要性", "意义", "有什么用", "干嘛要", "为什么要", "为何要",
        ]
        _fault_signals = ["差", "失败", "报错", "错误", "异常", "不对", "不工作",
                          "不行", "不好", "没法", "得不到", "不出", "不对劲", "不合格",
                          "不像", "不像蛋白", "不像结构", "不正常", "有问题",
                          "模糊", "不清晰", "看不清", "噪", "噪声", "条纹", "发糊"]
        if not any(s in state.user_input_lower for s in _fault_signals):
            if any(k in state.user_input_lower for k in concept_intro):
                return "", "concept_explain"

        # 参数解释、概念说明类问题 -> 交给 Expert Agent
        expert_triggers = [
            "是什么", "什么意思", "怎么理解", "解释", "含义", "定义",
            "怎么设", "如何设置", "参数", "建议", "推荐", "多少合适",
            "pixel size", "box size", "ctf", "分辨率", "voltage", "电压",
            "为什么", "原因", "原理", "作用", "影响",
            # V3 enhancement: more trigger words for better routing
            "合适", "阈值", "标准", "指标", "数值", "设置",
            "好坏", "判断", "评估", "怎么看", "解读",
            "异常", "失败", "报错", "问题", "出错", "错误",
            # 数量/选择类参数问题（如"做几个class""3个够吗""用多大"）
            "几个", "多少", "够吗", "够不够", "用多大", "选哪个",
            "class", "classes", "number of", "要不要",
        ]
        if any(k in state.user_input_lower for k in expert_triggers):
            return "", "param_advice"

        # 完成意图必须先于故障校验判断：否则用户说「完成了，没有报错」会因
        # 「报错」二字被 validate_feedback 误判为 failed，永远进不了 advance。
        complete_triggers = [
            "完成", "done", "通过", "ok", "没问题", "已经做好了", "已经完成了", "搞定了", "做完了",
            "ok了", "可以了", "继续下一步", "下一步吧", "已经弄好了", "弄好了", "已经处理好了", "处理好了",
            "已完成", "完成了", "做好了",
        ]
        if any(k in state.user_input_lower for k in complete_triggers):
            validation = self.input_validator.validate_feedback(user_text)
            self._mark_current(state, "passed", validation.summary)
            self._sync_cp_name(state)
            current = self._get_cp(state.current_cp_id)
            next_id = self._next_cp_id(state.current_cp_id) if current else None
            if not next_id:
                return "## 所有检查站已完成", "advance"
            next_cp = self._get_cp(next_id)
            state.current_cp_id = next_id
            state.current_cp_name = next_cp.get("checkpoint_cn", "") if next_cp else ""
            state.mark_checkpoint(state.current_cp_id, "in_progress", "进入下一站", user_text)
            return f"✅ 阶段已通过，进入下一阶段：{state.current_cp_name}。", "stage_guide_sop"

        validation = self.input_validator.validate_feedback(user_text)
        if not validation.passed:
            state.last_qc_result = validation.to_dict()
            self._mark_current(state, "failed", validation.summary)
            return self.diagnose(state, user_text), "fault_diagnosis"

        return self.get_stage_guide(state), "stage_guide"

    def advance(self, state: PipelineState) -> str:
        self._sync_cp_name(state)
        current = self._get_cp(state.current_cp_id)
        if not current:
            return "未找到当前检查站。"
        next_id = self._next_cp_id(state.current_cp_id)
        if not next_id:
            return "## 所有检查站已完成"
        next_cp = self._get_cp(next_id)
        state.current_cp_id = next_id
        state.current_cp_name = next_cp.get("checkpoint_cn", "") if next_cp else ""
        state.mark_checkpoint(state.current_cp_id, "in_progress", "进入下一站", state.user_input)
        return self.get_stage_guide(state, state.current_cp_id)

    def get_progress(self, state: PipelineState) -> str:
        total = len(self.checkpoints)
        return f"## 进度\n\n已完成 {len(state.completed)}/{total}，当前阶段：{state.current_cp_id} ({state.current_cp_name})"

    def generate_report(self, state: PipelineState) -> str:
        total = len(self.checkpoints)
        done = len(state.completed)
        pct = f"{(done / total * 100):.0f}%" if total else "0%"

        def _name(cp_id: str) -> str:
            cp = self._get_cp(cp_id)
            return f"{cp_id}（{cp.get('checkpoint_cn', '')}）" if cp else cp_id

        lines = [
            "## 流程报告",
            "",
            f"- **会话**：{getattr(state, 'session_name', '') or state.session_id}",
            f"- **软件**：{state.software}",
            f"- **当前阶段**：{_name(state.current_cp_id)}",
            f"- **整体进度**：{done}/{total} · {pct}",
            "",
            "### 检查站状态",
            f"- ✅ 已通过：{', '.join(_name(c) for c in state.completed) if state.completed else '无'}",
            f"- ❌ 未通过：{', '.join(_name(c) for c in state.failed) if state.failed else '无'}",
            f"- ⏭️ 已跳过：{', '.join(_name(c) for c in state.skipped) if state.skipped else '无'}",
        ]

        lines.extend(["", "### 已采集参数"])
        if state.params:
            lines.extend(f"- {k}：{v}" for k, v in state.params.items())
        else:
            lines.append("- 暂无")

        if state.last_qc_result:
            summary = state.last_qc_result.get("summary", "")
            suggestion = state.last_qc_result.get("suggestion", "")
            lines.extend(["", "### 最近一次 QC / 故障提示"])
            if summary:
                lines.append(f"- 概要：{summary}")
            if suggestion:
                lines.append(f"- 建议：{suggestion}")

        lines.extend(["", f"- 消息总数：{len(state.messages)}", f"- 更新时间：{state.last_updated}"])
        return "\n".join(lines)

    def diagnose(self, state: PipelineState, user_text: str) -> str:
        # 检查是否有进行中的诊断
        fault_state = state.fault_diagnosis_state
        active_id = fault_state.get("active_fault_id", "")

        # 如果有活跃诊断且有未问的问题，继续提问
        if active_id:
            fault = self._find_fault_by_id(active_id)
            if fault:
                questions = fault.get("questions", [])
                asked = fault_state.get("asked_questions", [])
                answers = fault_state.get("answers", {})
                pending = [q for q in questions if q["id"] not in asked]

                # 尝试从用户输入中解析当前问题的回答
                if pending and asked:
                    last_q = questions[len(asked) - 1] if len(asked) <= len(questions) else None
                    if last_q:
                        answers[last_q["id"]] = user_text[:200]
                        fault_state["answers"] = answers
                        asked.append(last_q["id"])
                        fault_state["asked_questions"] = asked

                # 还有未问的问题 → 继续提问
                pending = [q for q in questions if q["id"] not in asked]
                if pending:
                    return self._format_diagnosis_question(fault, pending[0], len(asked) + 1, len(questions))

                # 所有问题已回答 → 输出方案
                fault_state["active_fault_id"] = ""
                fault_state["asked_questions"] = []
                fault_state["answers"] = {}
                return self._format_solutions(fault, answers)

        # 无活跃诊断 → 匹配故障
        candidates = sorted(self._score_fault_candidates(user_text), key=lambda x: x["confidence"], reverse=True)
        if candidates and candidates[0].get("confidence", 0) > 0.3:
            best = candidates[0]
            questions = best.get("questions", [])
            if questions:
                # 启动交互式诊断
                fault_state["active_fault_id"] = best.get("fault_id", "")
                fault_state["asked_questions"] = []
                fault_state["answers"] = {}
                return self._format_diagnosis_intro(best) + "\n\n" + self._format_diagnosis_question(best, questions[0], 1, len(questions))
            # 旧格式（无 questions 字段）
            return self._format_fault_legacy(best)
        result = self.input_validator.validate_feedback(user_text)
        return f"## 质控提示\n\n{result.summary}\n\n{result.suggestion}"

    def _score_fault_candidates(self, user_text: str):
        lowered = user_text.lower()
        scored = []
        for fault in self.faults:
            score = 0.0
            keywords = []
            kw1 = fault.get("fault_keyword")
            if kw1:
                keywords.append(kw1)
            keywords.extend(fault.get("fault_keywords", []))
            for kw in keywords:
                if kw and kw.lower() in lowered:
                    score += 0.45
            phenomenon = fault.get("phenomenon", "").lower()
            if any(tok in lowered for tok in phenomenon.split() if len(tok) > 1):
                score += 0.25
            score = min(score, 0.99)
            if score > 0:
                scored.append({**fault, "confidence": round(score, 2)})
        if not scored:
            scored = [{**fault, "confidence": 0.2} for fault in self.faults]
        return scored

    def _format_fault_response(self, matched: Dict[str, Any], candidates, reasons, rollback) -> str:
        reasons_text = "\n".join(f"- {r}" for r in reasons) if reasons else "- 未提供"
        rollback_text = "\n".join(f"- {r}" for r in rollback) if rollback else "- 无"
        cand_text = "\n".join(
            f"{i+1}. {c.get('phenomenon', c.get('fault_keyword', '未知'))}  |  置信度 {c.get('confidence', 0):.2f}"
            for i, c in enumerate(candidates[:3])
        )
        return (
            f"## 故障诊断：{matched.get('phenomenon', '未知')}\n\n"
            f"**可能原因**\n{reasons_text}\n\n"
            f"**建议**\n{matched.get('solve_suggest', '')}\n\n"
            f"**建议回溯节点**\n{rollback_text}\n\n"
            f"**候选诊断排序**\n{cand_text}"
        )

    def _search_fault(self, user_text: str) -> Optional[Dict[str, Any]]:
        lowered = user_text.lower()
        best_score = 0
        best = None
        for fault in self.faults:
            score = 0
            keywords = [fault.get("fault_keyword", "")]
            keywords.extend(fault.get("fault_keywords", []))
            for kw in keywords:
                if kw and kw.lower() in lowered:
                    score += 2
            phenomenon = fault.get("phenomenon", "")
            if any(tok in lowered for tok in phenomenon.lower().split() if len(tok) > 1):
                score += 1
            if score > best_score:
                best_score = score
                best = fault
        return best if best_score > 0 else None

    def _find_fault_by_id(self, fault_id: str) -> Optional[Dict[str, Any]]:
        for fault in self.faults:
            if fault.get("fault_id") == fault_id:
                return fault
        return None

    def _format_diagnosis_intro(self, fault: Dict[str, Any]) -> str:
        title = fault.get("title_cn", fault.get("fault_keyword", ""))
        symptom = fault.get("symptom_cn", fault.get("phenomenon", ""))
        severity = fault.get("severity", "warning")
        icon = {"problem": "\u274c", "warning": "\u26a0\ufe0f", "good": "\U0001F7E2"}.get(severity, "\u2139\ufe0f")
        return (
            f"## \U0001FA7A 排障诊断：{title}\n\n"
            f"{icon} **症状**: {symptom}\n\n"
            f"我将逐步帮你诊断问题原因，请回答以下问题："
        )

    def _format_diagnosis_question(self, fault: Dict[str, Any], question: Dict[str, str], num: int, total: int) -> str:
        title = fault.get("title_cn", fault.get("fault_keyword", ""))
        return (
            f"### \U0001FA7A 排障诊断：{title}（问题 {num}/{total}）\n\n"
            f"**{question.get('text_cn', '')}**\n\n"
            f"*{question.get('impact_cn', '')}*\n\n"
            f"请回答「是」或「否」，或描述具体情况。"
        )

    def _format_solutions(self, fault: Dict[str, Any], answers: Dict[str, str]) -> str:
        title = fault.get("title_cn", fault.get("fault_keyword", ""))
        solutions = fault.get("solutions", [])
        lines = [f"## \U0001FA7A 排障诊断：{title} \u2014 解决方案", ""]
        lines.append("根据你的回答，以下是按优先级排序的解决方案：")
        lines.append("")

        for sol in sorted(solutions, key=lambda s: s.get("priority", 99)):
            priority = sol.get("priority", "?")
            action = sol.get("action_cn", "")
            reason = sol.get("reason_cn", "")
            trade_off = sol.get("trade_off_cn", "")
            source = sol.get("source", "")

            lines.append(f"### \U0001F522 方案 {priority}：{action}")
            if reason:
                lines.append(f"**原因**: {reason}")
            if trade_off:
                lines.append(f"\u26a0\ufe0f **代价**: {trade_off}")
            if source:
                lines.append(f"*\U0001F4D8 {source}*")
            lines.append("")

        lines.append("---")
        lines.append("\U0001F4A1 建议按优先级从方案 1 开始尝试。如果问题仍未解决，可以回复具体症状继续诊断。")
        return "\n".join(lines)

    def _format_fault_legacy(self, matched: Dict[str, Any]) -> str:
        reasons = matched.get("possible_reason", [])
        rollback = matched.get("rollback_node", [])
        reasons_text = "\n".join(f"- {r}" for r in reasons) if reasons else "- 未提供"
        rollback_text = "\n".join(f"- {r}" for r in rollback) if rollback else "- 无"
        return (
            f"## 故障诊断：{matched.get('phenomenon', '未知')}\n\n"
            f"**可能原因**\n{reasons_text}\n\n"
            f"**建议**\n{matched.get('solve_suggest', '')}\n\n"
            f"**建议回溯节点**\n{rollback_text}"
        )

    def _inject_recommendations(self, state: PipelineState, cp: Dict[str, Any]) -> list:
        if not state.user_context:
            return []

        agent = self._get_recommend_agent()
        lines = []
        key_params = cp.get("cryosparc", {}).get("key_params", []) or cp.get("relion", {}).get("key_params", [])

        for param in key_params:
            rec = agent.recommend(param, state.user_context)
            if rec:
                lines.append(f"- \U0001F4A1 **推荐 {param}**: {rec['value']}（{rec['reason']}）")

        if lines:
            lines.insert(0, "**\U0001F4A1 个性化推荐**:")
        return lines

    def _inject_decision_hint(self, cp: Dict[str, Any]) -> list:
        decision_tree = cp.get("decision_tree")
        if not decision_tree:
            return []

        lines = [
            "### \U0001F500 选择引导",
            "",
            decision_tree.get("title", "请回答以下问题，系统将推荐最适合的方案："),
            "",
        ]
        for i, q in enumerate(decision_tree.get("questions", []), 1):
            lines.append(f"**Q{i}**: {q.get('text', '')}")
            for opt in q.get("options", []):
                lines.append(f"  - {opt.get('label', '')}")
            lines.append("")

        lines.append("请回答以上问题（如「球状蛋白」「有模板」「对比度好」），我将推荐最适合的 Picker 和完整路径。")
        return lines

    def _inject_official_guide(self, cp: Dict[str, Any]) -> list:
        if not isinstance(self.official_guide, dict):
            return []

        cp_name = cp.get("checkpoint_name", "")
        mapping = {
            "data_import": "import_movies",
            "motion_correction": "patch_motion",
            "ctf_estimation": "patch_ctf",
            "particle_picking": "blob_picker",
            "particle_extraction": "extract",
            "class_2d": "2d_classification",
            "ab_initio": "ab_initio",
            "class_3d": "heterogeneous",
            "refine_3d": "homogeneous",
            "ctf_refinement": "patch_ctf",
            "post_processing": "non_uniform",
        }
        matched_key = mapping.get(cp_name, "")
        if not matched_key:
            return []

        guide = self.official_guide.get(matched_key)
        if not guide:
            return []

        lines = ["### \U0001F4D8 官方文档"]
        desc = guide.get("description", "")
        if desc:
            lines.append(desc)
        url = guide.get("source_url", "")
        if url:
            lines.append(f"[查看 CryoSPARC Guide 原文 \u2197]({url})")
        return lines

    def _get_plot_agent(self):
        if self._plot_agent is None:
            from agents.plot_agent import PlotAgent
            self._plot_agent = PlotAgent()
        return self._plot_agent

    def _get_recommend_agent(self):
        if self._recommend_agent is None:
            from agents.recommend_agent import RecommendAgent
            self._recommend_agent = RecommendAgent()
        return self._recommend_agent
