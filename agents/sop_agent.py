"""SOP Agent.

Turns workflow knowledge into step-by-step operating procedures.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from graph.state import PipelineState
from knowledge_base.paths import iter_runtime_allowed_docs, load_json_with_fallback

# Performance: cached JSON loader
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False


def _cached_load(knowledge_dir: str, name: str, legacy_name: Optional[str] = None, default: Any = None) -> Any:
    if _HAS_ST:
        from utils.perf_cache import cached_load_json
        return cached_load_json(name, legacy_name or "", default if default is not None else {})
    return load_json_with_fallback(knowledge_dir, name, legacy_name, default=default)


class SOPAgent:
    def __init__(self, knowledge_dir: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.knowledge_dir = knowledge_dir or os.path.join(base, "knowledge_base")
        # Performance: use cached JSON loading
        self.templates = _cached_load(self.knowledge_dir, "sop_template.json")
        self.checkpoints = _cached_load(self.knowledge_dir, "flows/pipeline_checkpoints.json", "pipeline_checkpoints.json")
        self.relion_stage_cards = _cached_load(self.knowledge_dir, "flows/relion_stage_cards.json", "relion_stage_cards.json")

    def _load_json(self, name: str, legacy_name: Optional[str] = None) -> Any:
        return load_json_with_fallback(self.knowledge_dir, name, legacy_name, default={})

    def _get_cp(self, cp_id: str) -> Optional[Dict[str, Any]]:
        for cp in self.checkpoints:
            if cp.get("checkpoint_id") == cp_id:
                return cp
        return None

    def _get_relion_stage_card(self, cp_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(self.relion_stage_cards, list):
            return None
        for card in self.relion_stage_cards:
            if isinstance(card, dict) and card.get("id") == cp_id:
                return card
        return None

    def _load_formal_docs(self, cp_id: str) -> List[Dict[str, Any]]:
        governed_docs = [
            doc for doc in iter_runtime_allowed_docs(self.knowledge_dir)
            if doc.get("checkpoint_id") == cp_id
        ]
        if governed_docs:
            return governed_docs

        path = os.path.join(self.knowledge_dir, "knowledge_index.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                docs = json.load(f)
        except Exception:
            return []
        if not isinstance(docs, list):
            return []

        def _is_formal(doc: Dict[str, Any]) -> bool:
            if doc.get("checkpoint_id") != cp_id:
                return False
            status = doc.get("status")
            if status == "formal_ready":
                return True
            if status and status != "formal_ready":
                return False
            tags = doc.get("tags") or []
            return "formal_ready" in " ".join(tags)

        return [doc for doc in docs if isinstance(doc, dict) and _is_formal(doc)]

    def _append_list(self, lines: List[str], title: str, items: Any) -> None:
        if not isinstance(items, list):
            return
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        if not cleaned:
            return
        lines.extend(["", f"### {title}"])
        for item in cleaned:
            lines.append(f"- {item}")

    def _relion_sop(self, state: PipelineState, card: Dict[str, Any]) -> str:
        cp_id = str(card.get("id") or state.current_cp_id)
        label = str(card.get("label_cn") or card.get("name") or cp_id)
        lines: List[str] = [f"## SOP: {label}", ""]

        # 改动5：RELION SOP也增加流程位置概述
        cp = self._get_cp(cp_id)
        if cp:
            prev_cp = cp.get("prev_checkpoint", "")
            next_cp = cp.get("next_checkpoint", "")
            if prev_cp or next_cp:
                lines.append("### 📌 流程位置")
                if prev_cp:
                    lines.append(f"⬅️ 上一步：{prev_cp}")
                lines.append(f"🔹 **当前：{cp_id} — {label}**")
                if next_cp:
                    lines.append(f"➡️ 下一步：{next_cp}")
                lines.append("")

        goal = str(card.get("goal") or "").strip()
        if goal:
            lines.extend(["### 目标", goal])
        self._append_list(lines, "输入", card.get("inputs"))
        self._append_list(lines, "RELION Job", card.get("relion_jobs"))
        self._append_list(lines, "关键参数", card.get("key_parameters"))
        self._append_list(lines, "建议操作路线", card.get("starter_questions"))
        self._append_list(lines, "QC 检查", card.get("qc_checks"))
        self._append_list(lines, "常见坑", card.get("common_pitfalls"))

        formal_docs = self._load_formal_docs(cp_id)
        if formal_docs:
            lines.extend(["", "### 已审核问答补充"])
            for doc in formal_docs[:3]:
                title = str(doc.get("title_cn") or "").strip()
                answer = ""
                steps = doc.get("action_steps") or []
                if steps:
                    answer = str(steps[0]).strip()
                if title:
                    lines.append(f"- {title}")
                if answer:
                    lines.append(f"  {answer}")

        return "\n".join(lines)

    def build_step_list(self, state: PipelineState, stage_name: str, steps: List[str]) -> str:
        lines = [f"## SOP：{stage_name}", ""]

        # 改动5：增加workflow概述，帮助用户理解当前步骤在完整流程中的位置
        cp = self._get_cp(state.current_cp_id)
        if cp:
            prev_cp = cp.get("prev_checkpoint", "")
            next_cp = cp.get("next_checkpoint", "")
            if prev_cp or next_cp:
                lines.append("### 📌 流程位置")
                if prev_cp:
                    lines.append(f"⬅️ 上一步：{prev_cp}")
                lines.append(f"🔹 **当前：{state.current_cp_id} — {stage_name}**")
                if next_cp:
                    lines.append(f"➡️ 下一步：{next_cp}")
                lines.append("")

        lines.append("### 操作步骤")
        for i, step in enumerate(steps, start=1):
            lines.append(f"{i}. {step}")
        lines.append("")
        return "\n".join(lines)

    def quick_sop(self, state: PipelineState) -> str:
        if state.software == "relion":
            relion_card = self._get_relion_stage_card(state.current_cp_id)
            if relion_card:
                return self._relion_sop(state, relion_card)

        cp = self._get_cp(state.current_cp_id)
        if not cp:
            return "未找到当前阶段的 SOP。"
        cp_id = cp.get("checkpoint_id")
        template_name = next(iter(self.templates.keys()), None)
        template = self.templates.get(template_name, {}) if template_name else {}
        flow_steps = template.get("flow_steps", [])
        detail = template.get("step_detail", {})
        detail_text = detail.get(cp_id, cp.get("stage_goal", ""))
        steps = []
        software = state.software if state.software in ("cryosparc", "relion") else "relion"
        guide = cp.get(software, cp.get("relion", {}))
        relion_card = self._get_relion_stage_card(state.current_cp_id)
        if relion_card and not (guide.get("key_steps") or []):
            return self._relion_sop(state, relion_card)
        for s in guide.get("key_steps", []):
            steps.append(s)
        if not steps:
            steps = [detail_text]
        rendered = self.build_step_list(state, cp.get("checkpoint_cn", cp_id), steps)
        if flow_steps:
            flow_desc = " → ".join(flow_steps)
            rendered += f"\n\n**关联流程**：{flow_desc}"
        return rendered
