"""StructPilot v6.0 — CryoSPARC 风格流程图可视化。

使用 Graphviz 渲染精美的 Workflow 流程图。
"""

from __future__ import annotations


def generate_cryosparc_workflow_graph(checkpoints: list[dict], current_step: str = "") -> str:
    """生成 CryoSPARC 风格的流程图（Graphviz DOT 格式）。

    Parameters
    ----------
    checkpoints
        步骤列表
    current_step
        当前步骤 ID（高亮显示）

    Returns
    -------
    str
        Graphviz DOT 格式的图定义
    """
    # CryoSPARC 配色方案
    NODE_COLOR = "#4A90E2"  # 蓝色
    NODE_CURRENT = "#F5A623"  # 橙色（当前步骤）
    NODE_COMPLETED = "#7ED321"  # 绿色（已完成）
    EDGE_COLOR = "#D0D0D0"  # 灰色连线

    lines = [
        "digraph CryoSPARC_Workflow {",
        "    rankdir=LR;",  # 横向布局
        "    node [shape=box, style=\"rounded,filled\", fontname=\"Arial\", fontsize=10];",
        "    edge [color=\"" + EDGE_COLOR + "\", penwidth=2];",
        "    bgcolor=\"transparent\";",
        "",
    ]

    for i, cp in enumerate(checkpoints):
        cp_id = cp.get("checkpoint_id", f"cp_{i+1:02d}")
        cp_cn = cp.get("checkpoint_cn", cp.get("checkpoint_name", f"步骤{i+1}"))

        # 节点颜色
        if cp_id == current_step:
            fill_color = NODE_CURRENT
            font_color = "white"
        else:
            fill_color = NODE_COLOR
            font_color = "white"

        # 节点标签（带换行）
        label = f"{i+1}. {cp_cn}"
        if len(label) > 15:
            # 长标签换行
            words = label.split()
            label_lines = []
            current_line = ""
            for word in words:
                if len(current_line + word) > 15:
                    label_lines.append(current_line.strip())
                    current_line = word + " "
                else:
                    current_line += word + " "
            if current_line:
                label_lines.append(current_line.strip())
            label = "\\n".join(label_lines)

        lines.append(
            f'    "{cp_id}" [label="{label}", '
            f'fillcolor="{fill_color}", fontcolor="{font_color}"];'
        )

    # 添加边（流程连线）
    for i in range(len(checkpoints) - 1):
        from_id = checkpoints[i].get("checkpoint_id", f"cp_{i+1:02d}")
        to_id = checkpoints[i+1].get("checkpoint_id", f"cp_{i+2:02d}")
        lines.append(f'    "{from_id}" -> "{to_id}";')

    lines.append("}")
    return "\n".join(lines)


def generate_compact_workflow_graph(checkpoints: list[dict], current_step: str = "") -> str:
    """生成紧凑的横向流程图（简化版，适合小屏幕）。

    Parameters
    ----------
    checkpoints
        步骤列表
    current_step
        当前步骤 ID

    Returns
    -------
    str
        Graphviz DOT 格式
    """
    lines = [
        "digraph Compact_Workflow {",
        "    rankdir=LR;",
        "    node [shape=circle, style=filled, width=0.5, fontsize=8, fixedsize=true];",
        "    edge [penwidth=1.5, color=\"#B0B0B0\"];",
        "    bgcolor=\"transparent\";",
        "",
    ]

    for i, cp in enumerate(checkpoints):
        cp_id = cp.get("checkpoint_id", f"cp_{i+1:02d}")

        if cp_id == current_step:
            fill_color = "#F5A623"
            font_color = "white"
        else:
            fill_color = "#4A90E2"
            font_color = "white"

        lines.append(
            f'    "{cp_id}" [label="{i+1}", '
            f'fillcolor="{fill_color}", fontcolor="{font_color}"];'
        )

    for i in range(len(checkpoints) - 1):
        from_id = checkpoints[i].get("checkpoint_id", f"cp_{i+1:02d}")
        to_id = checkpoints[i+1].get("checkpoint_id", f"cp_{i+2:02d}")
        lines.append(f'    "{from_id}" -> "{to_id}";')

    lines.append("}")
    return "\n".join(lines)
