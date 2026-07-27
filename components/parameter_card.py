"""优雅的参数卡片组件 - 参考 cryoSPARC 原生界面风格

设计原则：
- 紧凑的可折叠卡片
- 标签在输入框上方（节省横向空间）
- 灰白配色（专业、不花哨）
- 右侧清除按钮恢复默认值
- 减少纵向空间占用

用法：
    from components.parameter_card import render_parameter_section

    params = render_parameter_section(
        recommended_params={...},
        user_profile={...},
        current_values={...}
    )
"""

from __future__ import annotations
import streamlit as st
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ParameterConfig:
    """参数配置"""
    key: str
    label: str
    default: Any
    unit: str
    help_text: str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    param_type: str = "number"  # number, text, select
    options: Optional[list] = None


# 参数配置定义
MICROSCOPE_PARAMS = [
    ParameterConfig(
        key="voltage",
        label="加速电压",
        default=300,
        unit="kV",
        help_text="电镜加速电压，常见值为 200kV 或 300kV",
        min_val=80.0,
        max_val=400.0,
        step=1.0,
        param_type="number"
    ),
    ParameterConfig(
        key="Cs",
        label="球差系数",
        default=2.7,
        unit="mm",
        help_text="镜头球差系数，Titan Krios 通常为 2.7mm",
        min_val=0.1,
        max_val=10.0,
        step=0.1,
        param_type="number"
    ),
    ParameterConfig(
        key="pixel_size",
        label="像素大小",
        default=1.0,
        unit="Å/px",
        help_text="校准后的像素大小，影响分辨率和计算量",
        min_val=0.1,
        max_val=5.0,
        step=0.01,
        param_type="number"
    ),
    ParameterConfig(
        key="total_dose",
        label="总剂量",
        default=60.0,
        unit="e⁻/Å²",
        help_text="整个曝光过程的累积电子剂量",
        min_val=10.0,
        max_val=200.0,
        step=1.0,
        param_type="number"
    ),
]

SAMPLE_PARAMS = [
    ParameterConfig(
        key="particle_diameter",
        label="颗粒直径",
        default=150,
        unit="Å",
        help_text="颗粒的近似直径，用于自动挑选",
        min_val=50.0,
        max_val=1000.0,
        step=10.0,
        param_type="number"
    ),
    ParameterConfig(
        key="box_size",
        label="Box 大小",
        default=256,
        unit="px",
        help_text="提取颗粒的方框大小。常用值为 128、192、256、320、384、512 px",
        min_val=64.0,
        max_val=2048.0,
        step=1.0,
        param_type="number"
    ),
]

PROCESSING_PARAMS = [
    ParameterConfig(
        key="bfactor",
        label="B-factor",
        default=-150,
        unit="Å²",
        help_text="用于锐化/平滑的温度因子",
        min_val=-500.0,
        max_val=0.0,
        step=10.0,
        param_type="number"
    ),
]


def _render_param_input_compact(
    param: ParameterConfig,
    current_value: Any,
    recommended_value: Any,
    ai_reason: str = ""
) -> Any:
    """渲染单个参数的输入控件（紧凑版）

    输入框独占整个可用宽度，不再为重置按钮单独分列——参数栏本身已经很窄。
    与推荐值不同时在下方以 caption 提示，兼作"已被修改"的视觉标记。

    Returns:
        用户输入的新值
    """
    label = f"{param.label} ({param.unit})" if param.unit else param.label

    if param.param_type == "select" and param.options:
        new_value = st.selectbox(
            label,
            options=param.options,
            index=param.options.index(current_value) if current_value in param.options else 0,
            key=f"param_{param.key}",
            help=param.help_text,
        )
    elif param.param_type == "number":
        # 统一转 float，避免 st.number_input 的混合类型报错
        value_float = float(current_value) if current_value is not None else float(param.default)
        min_float = float(param.min_val) if param.min_val is not None else None
        max_float = float(param.max_val) if param.max_val is not None else None
        step_float = float(param.step) if param.step is not None else None

        new_value = st.number_input(
            label,
            value=value_float,
            min_value=min_float,
            max_value=max_float,
            step=step_float,
            key=f"param_{param.key}",
            help=param.help_text,
        )
    else:
        new_value = st.text_input(
            label,
            value=str(current_value) if current_value is not None else str(param.default),
            key=f"param_{param.key}",
            help=param.help_text,
        )

    if recommended_value is not None and new_value != recommended_value:
        tip = f"推荐 {recommended_value} {param.unit}".strip()
        if ai_reason:
            tip += f" · {ai_reason}"
        st.caption(tip)

    return new_value


# 流程步骤显示名（与 onboarding_v2 保持一致）
_STEP_NAMES = {
    "cp_01": "Import Movies",
    "cp_02": "Motion Correction",
    "cp_03": "CTF Estimation",
    "cp_04": "Blob Picker",
    "cp_05": "Extract Particles",
    "cp_06": "2D Classification",
    "cp_07": "Select 2D",
    "cp_08": "Initial Model",
    "cp_09": "3D Classification",
    "cp_10": "3D Refinement",
    "cp_11": "Post-processing",
}

# 参数归属的流程步骤，用于在流程图上标出"当前正在配置哪一步"
_PARAM_STEP = {
    "voltage": "cp_01",
    "Cs": "cp_01",
    "pixel_size": "cp_01",
    "total_dose": "cp_01",
    "particle_diameter": "cp_04",
    "box_size": "cp_05",
    "bfactor": "cp_11",
}


def _render_workflow_flow(active_steps: list[str], skip_steps: list[str]) -> None:
    """在右侧渲染竖向流程图（cryoSPARC 风格的节点卡片 + 连线）。"""
    st.markdown("##### 流程预览")

    css = """
<style>
.sp-flow { padding: 4px 0 0 2px; }
.sp-flow-node {
  display: flex; align-items: center; gap: 8px;
  border: 1px solid #d9e2ef; border-radius: 6px;
  background: #fff; padding: 7px 10px; font-size: 0.82rem;
}
.sp-flow-node.skip { background: #f8fafc; border-style: dashed; color: #94a3b8; }
.sp-flow-node .jid {
  background: #e0edff; color: #1d4ed8; border-radius: 4px;
  padding: 1px 6px; font-size: 0.72rem; font-weight: 700; font-family: ui-monospace, monospace;
}
.sp-flow-node.skip .jid { background: #eef2f7; color: #b0bac7; }
.sp-flow-link { width: 1px; height: 10px; background: #cbd5e1; margin: 0 0 0 22px; }
.sp-flow-link.skip { background: transparent; border-left: 1px dashed #dbe3ef; }
</style>
"""

    parts = [css, '<div class="sp-flow">']
    order = [f"cp_{i:02d}" for i in range(1, 12)]
    rendered = 0
    for step_id in order:
        is_active = step_id in active_steps
        if not is_active and step_id not in skip_steps:
            continue
        cls = "" if is_active else " skip"
        if rendered:
            parts.append(f'<div class="sp-flow-link{cls}"></div>')
        num = step_id.split("_")[1]
        name = _STEP_NAMES.get(step_id, step_id)
        parts.append(
            f'<div class="sp-flow-node{cls}"><span class="jid">J{int(num)}</span>'
            f'<span>{name}</span></div>'
        )
        rendered += 1
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

    if skip_steps:
        st.caption(f"实线 = 需执行（{len(active_steps)} 步）；虚线 = 已跳过（{len(skip_steps)} 步）")

def render_parameter_section(
    recommended_params: Dict[str, Any],
    user_profile: Dict[str, Any],
    current_values: Optional[Dict[str, Any]] = None,
    ai_reasons: Optional[Dict[str, str]] = None,
    workflow: Optional[Dict[str, Any]] = None,
    split_layout: bool = False,
) -> Dict[str, Any]:
    """渲染完整的参数配置界面（紧凑版，参考cryoSPARC风格）

    Parameters
    ----------
    recommended_params : dict
        AI 推荐的参数值
    user_profile : dict
        用户问卷信息（用于生成推荐理由）
    current_values : dict, optional
        当前参数值（用户之前的设置）
    ai_reasons : dict, optional
        AI 推荐理由，key 为参数名，value 为理由文本
    workflow : dict, optional
        推荐流程（含 steps / skip_steps），用于在右栏绘制流程图
    split_layout : bool
        True 时采用 cryoSPARC 式左窄右宽布局：左侧参数栏，右侧流程图。
        在 sidebar 等本身很窄的容器里调用应保持 False。

    Returns
    -------
    dict
        用户确认后的参数字典
    """
    if current_values is None:
        current_values = {}

    if ai_reasons is None:
        ai_reasons = {}

    result_params = {}

    # cryoSPARC风格CSS
    st.markdown("""
    <style>
    /* 紧凑的卡片样式 */
    div[data-testid="stExpander"] {
        background-color: #f7f7f7;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        margin-bottom: 8px;
    }

    /* 减少expander内部padding */
    div[data-testid="stExpander"] > div > div {
        padding-top: 8px !important;
        padding-bottom: 8px !important;
    }

    /* 输入框样式优化 */
    div[data-baseweb="select"],
    div[data-baseweb="input"] {
        font-size: 14px;
    }

    /* 紧凑的按钮 */
    .stButton button {
        padding: 4px 8px;
        font-size: 16px;
        line-height: 1;
    }

    /* 标题样式 */
    h2 {
        font-size: 20px;
        margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🔧 参数配置")
    st.caption("AI 已根据你的需求预填推荐值，按实际情况修改即可。")

    # cryoSPARC 式布局：左侧窄参数栏，右侧流程图
    if split_layout:
        col_params, col_flow = st.columns([1, 2], gap="large")
    else:
        col_params, col_flow = st.container(), None

    with col_params:
        # 需求概览（紧凑：单列 caption，避免在窄栏里挤成三列）
        if user_profile:
            with st.expander("📋 需求概览", expanded=False):
                if user_profile.get("sample_type"):
                    st.caption(f"样品类型 · {user_profile['sample_type']}")
                if user_profile.get("target_resolution"):
                    st.caption(f"目标分辨率 · {user_profile['target_resolution']} Å")
                if user_profile.get("microscope"):
                    st.caption(f"设备 · {user_profile['microscope']}")

        for title, group, default_open in (
            ("🔬 显微镜参数", MICROSCOPE_PARAMS, True),
            ("🧬 样品参数", SAMPLE_PARAMS, True),
            ("⚙️ 处理参数", PROCESSING_PARAMS, False),
        ):
            with st.expander(title, expanded=default_open):
                for param in group:
                    result_params[param.key] = _render_param_input_compact(
                        param,
                        current_values.get(param.key, param.default),
                        recommended_params.get(param.key, param.default),
                        ai_reasons.get(param.key, ""),
                    )

        st.divider()
        confirmed = st.button(
            "✅ 确认参数", type="primary", use_container_width=True, key="confirm_params"
        )
        if st.button("↺ 全部重置", use_container_width=True, key="reset_all_params"):
            for param in MICROSCOPE_PARAMS + SAMPLE_PARAMS + PROCESSING_PARAMS:
                st.session_state.pop(f"param_{param.key}", None)
            st.rerun()

    if col_flow is not None:
        with col_flow:
            wf = workflow or {}
            active = wf.get("steps") or [f"cp_{i:02d}" for i in range(1, 12)]
            skipped = wf.get("skip_steps") or []
            _render_workflow_flow(active, skipped)
            if wf.get("reason"):
                st.caption(wf["reason"])

    # Preserve edited onboarding/workflow parameters that are not rendered by
    # this compact panel (for example mask_diameter or num_classes_2d).
    return {**current_values, **result_params} if confirmed else None
