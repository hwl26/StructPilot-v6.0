"""StructPilot v6.0 — 工作流路线图渲染。

用 Graphviz 把推荐流程画成灵动的节点图：
- 需要做的步骤：高亮
- 跳过的步骤：灰色虚线
- 当前步骤：主题色描边
- 阶段分组：用 phase 分子图

数据来源为 knowledge_base/flows/pipeline_checkpoints.json，不硬编码步骤名。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
_CHECKPOINTS_PATH = BASE_DIR / "knowledge_base" / "flows" / "pipeline_checkpoints.json"


def load_checkpoints() -> list[dict]:
    """加载 12 步 checkpoint 定义（按 order 排序）。"""
    try:
        data = json.loads(_CHECKPOINTS_PATH.read_text(encoding="utf-8"))
        return sorted(data, key=lambda c: c.get("order", 0))
    except Exception:
        return []


def _short_id(cp_id: str) -> str:
    """cp_01 -> 01，用作 graphviz 节点 id（避免特殊字符）。"""
    return cp_id.replace("cp_", "n")


def _escape_tooltip(text: str) -> str:
    """转义 tooltip 中的特殊字符（引号、换行）。"""
    return text.replace("\\", "\\\\").replace('"', "'").replace("\n", "&#10;")


def _build_tooltip(cp: dict) -> str:
    """从 checkpoint 构建悬浮提示：这步目标 + 常见坑。"""
    parts = []
    goal = cp.get("stage_goal", "")
    if goal:
        parts.append(f"🎯 目标：{goal}")

    pitfalls = cp.get("common_pitfalls", [])
    if isinstance(pitfalls, list) and pitfalls:
        parts.append("⚠️ 常见坑：")
        for p in pitfalls[:2]:  # 最多2条，避免 tooltip 过长
            parts.append(f"  • {p}")

    inputs = cp.get("input_needed", "")
    if inputs:
        parts.append(f"📥 需要：{inputs}")

    return _escape_tooltip("\n".join(parts)) if parts else "点击进入该步骤查看详情"


def build_workflow_dot(
    workflow: dict,
    current_cp_id: str = "",
    theme_accent: str = "#3b82f6",
    is_dark: bool = False,
) -> str:
    """根据推荐工作流生成 Graphviz DOT 字符串。

    Parameters
    ----------
    workflow
        {"steps": [...], "skip_steps": [...], ...}
    current_cp_id
        当前所在步骤，用主题色描边高亮。
    theme_accent
        主题强调色（十六进制）。
    is_dark
        是否暗色主题，决定文字和背景色。
    """
    checkpoints = load_checkpoints()
    if not checkpoints:
        return "digraph G { label=\"（流程数据缺失）\"; }"

    steps = set(workflow.get("steps", []))
    skip_steps = set(workflow.get("skip_steps", []))

    # 归一化：pipeline_checkpoints 用 cp_01，workflow 可能用 cp_1
    def _norm(cid: str) -> str:
        if cid.startswith("cp_") and len(cid) == 4:  # cp_1 -> cp_01
            return f"cp_{int(cid[3:]):02d}"
        return cid

    steps = {_norm(s) for s in steps}
    skip_steps = {_norm(s) for s in skip_steps}
    current_norm = _norm(current_cp_id) if current_cp_id else ""

    text_color = "#e2e8f0" if is_dark else "#1e293b"
    bg_skip = "#334155" if is_dark else "#f1f5f9"
    skip_text = "#94a3b8" if is_dark else "#94a3b8"
    active_fill = f"{theme_accent}22"

    lines = [
        "digraph G {",
        "  rankdir=LR;",  # 横向布局，更宽矮紧凑
        "  bgcolor=\"transparent\";",
        "  nodesep=0.25;",  # 同 rank 节点间距
        "  ranksep=0.45;",  # rank 之间间距
        "  node [shape=box style=\"rounded,filled\" fontname=\"Microsoft YaHei,Arial\" "
        "fontsize=10 margin=\"0.12,0.07\" penwidth=1.4 height=0.4];",
        f"  edge [color=\"{theme_accent}\" penwidth=1.2 arrowsize=0.6];",
    ]

    # 按 phase 分组，用 subgraph cluster 呈现阶段
    phases: dict[str, list[dict]] = {}
    for cp in checkpoints:
        phase = cp.get("phase", "其他")
        phases.setdefault(phase, []).append(cp)

    cluster_idx = 0
    for phase, cps in phases.items():
        lines.append(f"  subgraph cluster_{cluster_idx} {{")
        lines.append(f"    label=\"{phase}\";")
        lines.append(f"    fontname=\"Microsoft YaHei,Arial\"; fontsize=10; fontcolor=\"{skip_text}\";")
        lines.append(f"    color=\"{skip_text}\"; style=\"dashed,rounded\";")
        for cp in cps:
            cid = cp.get("checkpoint_id", "")
            name = cp.get("checkpoint_cn", cp.get("checkpoint_name", cid))
            order = cp.get("order", 0)
            nid = _short_id(cid)
            label = f"{order}. {name}"

            is_skipped = cid in skip_steps or (steps and cid not in steps)
            is_current = cid == current_norm

            if is_current:
                fill = active_fill
                border = theme_accent
                pen = "2.5"
                fontc = text_color
                label = f"▶ {label}"
            elif is_skipped:
                fill = bg_skip
                border = skip_text
                pen = "1.0"
                fontc = skip_text
                label = f"⊝ {label}"
            else:
                fill = "#ffffff" if not is_dark else "#1e293b"
                border = theme_accent
                pen = "1.5"
                fontc = text_color

            style = "rounded,filled,dashed" if is_skipped else "rounded,filled"
            tooltip = _build_tooltip(cp)
            lines.append(
                f"    {nid} [label=\"{label}\" fillcolor=\"{fill}\" "
                f"color=\"{border}\" fontcolor=\"{fontc}\" penwidth={pen} style=\"{style}\" "
                f"tooltip=\"{tooltip}\"];"
            )
        lines.append("  }")
        cluster_idx += 1

    # 顺序连边
    ordered = [cp.get("checkpoint_id", "") for cp in checkpoints]
    for a, b in zip(ordered, ordered[1:]):
        na, nb = _short_id(a), _short_id(b)
        b_skipped = b in skip_steps or (steps and b not in steps)
        edge_style = "dashed" if b_skipped else "solid"
        lines.append(f"  {na} -> {nb} [style={edge_style}];")

    lines.append("}")
    return "\n".join(lines)
