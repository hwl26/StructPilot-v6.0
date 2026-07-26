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
        options=[200, 300],
        param_type="select"
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
        help_text="提取颗粒的方框大小，应为 2 的幂次",
        options=[128, 192, 256, 320, 384, 512],
        param_type="select"
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

    Returns:
        用户输入的新值
    """
    # 紧凑布局：左侧输入，右侧清除按钮
    col_input, col_reset = st.columns([5, 1])

    with col_input:
        # 显示 AI 推荐（如果与当前值不同）
        if recommended_value is not None and recommended_value != current_value:
            st.caption(f"💡 推荐：{recommended_value} {param.unit} - {ai_reason}")

        # 根据参数类型渲染输入控件
        if param.param_type == "select" and param.options:
            new_value = st.selectbox(
                f"{param.label} ({param.unit})",
                options=param.options,
                index=param.options.index(current_value) if current_value in param.options else 0,
                key=f"param_{param.key}",
                help=param.help_text,
                label_visibility="visible"
            )
        elif param.param_type == "number":
            # 确保类型一致性
            value_float = float(current_value) if current_value is not None else float(param.default)
            min_float = float(param.min_val) if param.min_val is not None else None
            max_float = float(param.max_val) if param.max_val is not None else None
            step_float = float(param.step) if param.step is not None else None

            new_value = st.number_input(
                f"{param.label} ({param.unit})",
                value=value_float,
                min_value=min_float,
                max_value=max_float,
                step=step_float,
                key=f"param_{param.key}",
                help=param.help_text,
                label_visibility="visible"
            )
        else:  # text
            new_value = st.text_input(
                f"{param.label} ({param.unit})",
                value=str(current_value) if current_value is not None else str(param.default),
                key=f"param_{param.key}",
                help=param.help_text,
                label_visibility="visible"
            )

    with col_reset:
        # 清除按钮（恢复默认值）
        st.markdown("<br>", unsafe_allow_html=True)  # 对齐按钮位置
        if st.button("↺", key=f"reset_{param.key}", help="恢复默认值"):
            new_value = param.default
            st.rerun()

    return new_value


def render_parameter_section(
    recommended_params: Dict[str, Any],
    user_profile: Dict[str, Any],
    current_values: Optional[Dict[str, Any]] = None,
    ai_reasons: Optional[Dict[str, str]] = None
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
    st.caption("AI 已根据您的需求推荐参数，可随时调整。点击 ↺ 恢复默认值。")

    # 显示用户画像（紧凑版）
    if user_profile:
        with st.expander("📋 需求概览", expanded=False):
            col1, col2, col3 = st.columns(3)
            if "sample_type" in user_profile:
                col1.caption("**样品类型**")
                col1.write(user_profile["sample_type"])
            if "target_resolution" in user_profile:
                col2.caption("**目标分辨率**")
                col2.write(f"{user_profile['target_resolution']} Å")
            if "microscope" in user_profile:
                col3.caption("**设备**")
                col3.write(user_profile["microscope"])

    # 1. 显微镜参数
    with st.expander("🔬 显微镜参数", expanded=True):
        for param in MICROSCOPE_PARAMS:
            current = current_values.get(param.key, param.default)
            recommended = recommended_params.get(param.key, param.default)
            reason = ai_reasons.get(param.key, "")

            result_params[param.key] = _render_param_input_compact(
                param, current, recommended, reason
            )

    # 2. 样品参数
    with st.expander("🧬 样品参数", expanded=True):
        for param in SAMPLE_PARAMS:
            current = current_values.get(param.key, param.default)
            recommended = recommended_params.get(param.key, param.default)
            reason = ai_reasons.get(param.key, "")

            result_params[param.key] = _render_param_input_compact(
                param, current, recommended, reason
            )

    # 3. 处理参数
    with st.expander("⚙️ 处理参数", expanded=False):
        for param in PROCESSING_PARAMS:
            current = current_values.get(param.key, param.default)
            recommended = recommended_params.get(param.key, param.default)
            reason = ai_reasons.get(param.key, "")

            result_params[param.key] = _render_param_input_compact(
                param, current, recommended, reason
            )

    # 确认按钮
    st.divider()
    col_confirm, col_cancel = st.columns([1, 1])
    with col_confirm:
        if st.button("✅ 确认参数", type="primary", use_container_width=True, key="confirm_params"):
            return result_params

    with col_cancel:
        if st.button("↺ 全部重置", use_container_width=True, key="reset_all_params"):
            st.rerun()

    return None  # 用户未点击确认
