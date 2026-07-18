"""PlotAgent — 图表解读智能体。

根据用户选择的图表类型和当前检查站，从 PLOT_INTERP_KB 匹配解读规则，
生成三级诊断报告（🟢 达标 / ⚠️ 警告 / ❌ 问题）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class PlotAgent:
    def __init__(self, kb_path: Optional[str] = None):
        if kb_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            kb_path = os.path.join(base, "knowledge_base", "plots", "plot_interp_kb.json")
        self.plot_kb: Dict[str, Any] = {}
        self._load_kb(kb_path)

    def _load_kb(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.plot_kb = json.load(f)
        except Exception:
            self.plot_kb = {}

    def list_plot_types_for_cp(self, cp_id: str) -> List[Dict[str, str]]:
        """列出当前检查站可解读的图表类型。"""
        available: List[Dict[str, str]] = []
        for plot_id, info in self.plot_kb.items():
            appears = info.get("appears_in", [])
            if cp_id in appears:
                available.append({
                    "id": plot_id,
                    "name": info.get("name_cn", info.get("name", plot_id)),
                })
        return available

    def interpret(self, plot_type: str, current_cp_id: str) -> str:
        """根据图表类型和当前步骤，返回 Markdown 格式的诊断报告。"""
        kb = self.plot_kb.get(plot_type)
        if not kb:
            return "未找到该图表类型的解读规则。可用的图表类型包括：FSC 曲线、取向分布图、ESS 直方图、类别平均图、NCC vs Power 图、Guinier 图、噪声模型图、后验精度方向分布。"

        lines = [f"## 📊 {kb.get('name_cn', kb.get('name', plot_type))} 解读", ""]

        if not kb.get("rules"):
            lines.append("暂无该图表类型的解读规则。")
            return "\n".join(lines)

        # 排序：problem > warning > info > good
        severity_order = {"problem": 0, "warning": 1, "info": 2, "good": 3}
        sorted_rules = sorted(
            kb.get("rules", []),
            key=lambda r: severity_order.get(r.get("severity", "info"), 99),
        )

        for rule in sorted_rules:
            icon = rule.get("icon", "ℹ️")
            meaning = rule.get("meaning_cn", "")
            action = rule.get("action_cn", "")

            lines.append(f"### {icon} {meaning}")
            if action:
                lines.append(f"**建议**: {action}")

            causes = rule.get("causes_cn", [])
            if causes:
                lines.append(f"**可能原因**: {'; '.join(causes)}")

            actions = rule.get("actions_cn", [])
            if actions:
                lines.append("**排查步骤**:")
                for i, a in enumerate(actions, 1):
                    lines.append(f"  {i}. {a}")

            source = rule.get("source", "")
            if source:
                lines.append(f"*📘 {source}*")

            lines.append("")

        # 重要提示
        note = kb.get("important_note", "")
        if note:
            lines.append(f"> ⚠️ **重要提示**: {note}")
            lines.append("")

        # 版本变化
        ver_changes = kb.get("version_changes", "")
        if ver_changes:
            lines.append(f"🆕 **版本变化**: {ver_changes}")
            lines.append("")

        # 列出当前 CP 相关的图表类型
        related = self.list_plot_types_for_cp(current_cp_id)
        if len(related) > 1:
            other_names = [r["name"] for r in related if r["id"] != plot_type]
            if other_names:
                lines.append(f"💡 当前步骤还可解读：{'、'.join(other_names)}")

        return "\n".join(lines)

    def detect_plot_type(self, user_text: str, cp_id: str) -> Optional[str]:
        """从用户输入中检测图表类型关键词。"""
        lowered = (user_text or "").lower()

        keyword_map = {
            "fsc_curve": ["fsc", "fourier shell", "分辨率曲线"],
            "orientation_distribution": ["取向", "orientation", "方向分布", "viewing direction"],
            "class_ess": ["ess", "有效样本", "effective sample"],
            "class_average": ["类别平均", "class average", "2d 类", "二维类"],
            "ncc_power": ["ncc", "power", "互相关"],
            "guinier": ["guinier", "b因子", "b-factor", "锐化"],
            "noise_model": ["噪声模型", "noise model", "噪声"],
            "posterior_precision": ["后验精度", "posterior precision"],
            "best_class_prob": ["最佳类别概率", "best class prob"],
        }

        for plot_id, keywords in keyword_map.items():
            if any(kw in lowered for kw in keywords):
                # 验证该图表类型在当前 CP 可用
                available = self.list_plot_types_for_cp(cp_id)
                available_ids = [a["id"] for a in available]
                if plot_id in available_ids:
                    return plot_id
                # 如果不可用但仍返回，至少给用户一个反馈
                return plot_id

        return None
