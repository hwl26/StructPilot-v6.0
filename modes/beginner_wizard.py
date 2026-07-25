"""StructPilot v6.0 — 入门模式参数填写向导

逐步引导小白用户填写 cryoSPARC workflow 参数：
1. 每个 job 一页（或多步合并为一页）
2. 核心参数（flagged=True）默认展开
3. 固定参数（locked=True）折叠且灰显
4. 最后生成 workflow JSON 供导出

调用方：main.py 入门模式 Tab
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import streamlit as st

from utils.cryosparc_workflow import generate_cryosparc_workflow, workflow_to_json_str


# 向导步骤定义（job分组）
_WIZARD_STEPS: List[Dict[str, Any]] = [
    {
        "title": "1. 数据导入",
        "description": "指定电影文件路径和采集参数",
        "jobs": ["cp_01"],  # Import Movies
        "icon": "📂",
    },
    {
        "title": "2. 预处理",
        "description": "Motion Correction 和 CTF 估计（参数已预设）",
        "jobs": ["cp_02", "cp_03", "cp_03b"],  # Motion + CTF + Curate
        "icon": "🔧",
    },
    {
        "title": "3. 颗粒挑选",
        "description": "设置颗粒大小范围",
        "jobs": ["cp_04", "cp_04c"],  # Blob Picker + Inspect
        "icon": "🎯",
    },
    {
        "title": "4. 颗粒提取",
        "description": "设置 box size",
        "jobs": ["cp_05"],  # Extract
        "icon": "📦",
    },
    {
        "title": "5. 2D 分类",
        "description": "设置类别数",
        "jobs": ["cp_06", "cp_06b"],  # 2D Class + Select
        "icon": "🗂️",
    },
    {
        "title": "6. 3D 重建（可选）",
        "description": "初始模型和精修",
        "jobs": ["cp_07", "cp_08", "cp_09"],  # AbInit + Hetero + Homo
        "icon": "🧊",
    },
]


# job 的参数描述（用于生成表单）
_JOB_PARAMS_CONFIG: Dict[str, List[Dict[str, Any]]] = {
    "cp_01": [
        {
            "key": "movies_path",
            "label": "电影文件路径",
            "type": "text",
            "required": True,
            "flagged": True,
            "placeholder": "/path/to/*.tif 或 *.eer",
            "help": "通配符路径，例如：/home/data/20260101/*.tif",
        },
        {
            "key": "gainref_path",
            "label": "Gain Reference 文件",
            "type": "text",
            "required": False,
            "flagged": True,
            "placeholder": "/path/to/gain.mrc",
            "help": "增益参考文件（可选），K2/K3 相机通常需要",
        },
        {
            "key": "pixel_size",
            "label": "像素大小 (Å/pixel)",
            "type": "number",
            "required": True,
            "flagged": True,
            "default": 0.41,
            "min": 0.1,
            "max": 5.0,
            "step": 0.01,
            "help": "显微镜的实际像素大小，通常 0.4-1.5 Å",
        },
        {
            "key": "voltage",
            "label": "加速电压 (kV)",
            "type": "number",
            "required": True,
            "flagged": False,
            "locked": True,
            "default": 300,
            "options": [200, 300],
            "help": "显微镜加速电压，通常为 200 或 300 kV",
        },
        {
            "key": "Cs",
            "label": "球差系数 (mm)",
            "type": "number",
            "required": True,
            "flagged": False,
            "locked": True,
            "default": 2.7,
            "help": "球差系数，通常为 2.7 mm",
        },
        {
            "key": "total_dose",
            "label": "总剂量 (e⁻/Ų)",
            "type": "number",
            "required": True,
            "flagged": False,
            "locked": True,
            "default": 60,
            "help": "总电子剂量，通常 40-80 e⁻/Ų",
        },
    ],
    "cp_02": [
        {
            "key": "motion_gpus",
            "label": "GPU 数量",
            "type": "number",
            "required": False,
            "flagged": False,
            "locked": True,
            "default": 4,
            "help": "Motion Correction 使用的 GPU 数量",
        },
    ],
    "cp_03": [],  # CTF 无需用户填写参数
    "cp_03b": [],  # Curate 无需参数
    "cp_04": [
        {
            "key": "particle_diameter",
            "label": "颗粒最小直径 (Å)",
            "type": "number",
            "required": True,
            "flagged": True,
            "default": 110,
            "min": 50,
            "max": 500,
            "step": 10,
            "help": "颗粒的最小直径，根据蛋白大小设置",
        },
        {
            "key": "particle_diameter_max",
            "label": "颗粒最大直径 (Å)",
            "type": "number",
            "required": True,
            "flagged": True,
            "default": 160,
            "min": 50,
            "max": 500,
            "step": 10,
            "help": "颗粒的最大直径，通常为最小直径的 1.2-1.5 倍",
        },
    ],
    "cp_04c": [],  # Inspect Picks 无需参数
    "cp_05": [
        {
            "key": "box_size",
            "label": "Box Size (像素)",
            "type": "number",
            "required": True,
            "flagged": True,
            "default": 320,
            "options": [256, 320, 384, 512],
            "help": "提取框大小，通常为颗粒直径的 1.5-2 倍（以像素计）",
        },
    ],
    "cp_06": [
        {
            "key": "class2d_num_classes",
            "label": "类别数",
            "type": "number",
            "required": True,
            "flagged": True,
            "default": 100,
            "options": [50, 100, 150, 200],
            "help": "2D 分类的类别数，颗粒越多可设置越多",
        },
    ],
    "cp_06b": [],  # Select 2D 无需参数
    "cp_07": [
        {
            "key": "abinit_num_classes",
            "label": "初始类别数",
            "type": "number",
            "required": False,
            "flagged": True,
            "default": 3,
            "options": [1, 2, 3, 4],
            "help": "Ab-Initio 初始模型数量，通常 2-3 个",
        },
    ],
    "cp_08": [],  # Hetero Refine 自动继承参数
    "cp_09": [],  # Homo Refine 自动继承参数
}


def render_beginner_wizard(
    state: Any,
    app: Any,
) -> None:
    """渲染入门模式参数填写向导。

    Parameters
    ----------
    state : AppState
        会话状态对象
    app : StructPilotApp
        应用实例
    """
    st.markdown("## 🎯 cryoSPARC Workflow 参数填写")
    st.caption("逐步填写关键参数，系统将自动生成可导入 cryoSPARC 的 workflow 文件。")

    # 初始化向导状态
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0
    if "wizard_params" not in st.session_state:
        st.session_state.wizard_params = {}

    current_step = st.session_state.wizard_step
    total_steps = len(_WIZARD_STEPS)

    # 进度条
    progress = (current_step + 1) / total_steps
    st.progress(progress, text=f"步骤 {current_step + 1}/{total_steps}")

    # 当前步骤信息
    step_config = _WIZARD_STEPS[current_step]
    st.markdown(f"### {step_config['icon']} {step_config['title']}")
    st.caption(step_config['description'])

    # 渲染当前步骤的参数表单
    with st.form(f"wizard_step_{current_step}"):
        for job_id in step_config["jobs"]:
            _render_job_params(job_id, st.session_state.wizard_params)

        st.markdown("---")
        col_prev, col_next = st.columns(2)

        with col_prev:
            if current_step > 0:
                prev_clicked = st.form_submit_button("⬅️ 上一步", use_container_width=True)
            else:
                prev_clicked = False

        with col_next:
            if current_step < total_steps - 1:
                next_clicked = st.form_submit_button("下一步 ➡️", use_container_width=True, type="primary")
                finish_clicked = False
            else:
                next_clicked = False
                finish_clicked = st.form_submit_button("✅ 完成并生成 Workflow", use_container_width=True, type="primary")

        if prev_clicked:
            st.session_state.wizard_step = max(0, current_step - 1)
            st.rerun()
        elif next_clicked:
            st.session_state.wizard_step = min(total_steps - 1, current_step + 1)
            st.rerun()
        elif finish_clicked:
            _generate_and_export_workflow(st.session_state.wizard_params, state, app)


def _render_job_params(job_id: str, params_store: Dict[str, Any]) -> None:
    """渲染单个 job 的参数输入表单。"""
    param_configs = _JOB_PARAMS_CONFIG.get(job_id, [])
    if not param_configs:
        return  # 无需用户填写参数的 job（如 curate, inspect）

    # 分层：核心参数 vs 固定参数
    core_params = [p for p in param_configs if p.get("flagged", False)]
    locked_params = [p for p in param_configs if p.get("locked", False)]
    other_params = [p for p in param_configs if not p.get("flagged", False) and not p.get("locked", False)]

    # 渲染核心参数（默认展开）
    if core_params:
        st.markdown("**核心参数**")
        for param in core_params:
            _render_param_input(param, params_store)

    # 渲染固定参数（折叠）
    if locked_params:
        with st.expander("🔒 固定参数（通常无需修改）", expanded=False):
            for param in locked_params:
                _render_param_input(param, params_store, disabled=True)

    # 渲染其他参数（折叠）
    if other_params:
        with st.expander("📦 高级参数（可选）", expanded=False):
            for param in other_params:
                _render_param_input(param, params_store)


def _render_param_input(param: Dict[str, Any], params_store: Dict[str, Any], disabled: bool = False) -> None:
    """渲染单个参数输入控件。"""
    key = param["key"]
    label = param["label"]
    param_type = param["type"]
    required = param.get("required", False)
    default = param.get("default")
    help_text = param.get("help", "")
    placeholder = param.get("placeholder", "")

    # 从 store 中恢复值
    current_value = params_store.get(key, default)

    if param_type == "text":
        value = st.text_input(
            label + (" *" if required else ""),
            value=current_value or "",
            placeholder=placeholder,
            help=help_text,
            disabled=disabled,
            key=f"param_{key}",
        )
        params_store[key] = value

    elif param_type == "number":
        options = param.get("options")
        if options:
            # 下拉选择
            try:
                index = options.index(current_value) if current_value in options else 0
            except (ValueError, TypeError):
                index = 0
            value = st.selectbox(
                label + (" *" if required else ""),
                options=options,
                index=index,
                help=help_text,
                disabled=disabled,
                key=f"param_{key}",
            )
        else:
            # 数字输入
            min_val = param.get("min", 0.0)
            max_val = param.get("max", 1000.0)
            step = param.get("step", 1.0 if isinstance(default, int) else 0.01)
            value = st.number_input(
                label + (" *" if required else ""),
                min_value=min_val,
                max_value=max_val,
                value=float(current_value) if current_value is not None else float(default),
                step=step,
                help=help_text,
                disabled=disabled,
                key=f"param_{key}",
            )
        params_store[key] = value


def _generate_and_export_workflow(params: Dict[str, Any], state: Any, app: Any) -> None:
    """生成 workflow JSON 并提供下载。"""
    # 构建 workflow 对象（StructPilot 格式）
    workflow = {
        "steps": [
            "cp_01", "cp_02", "cp_03", "cp_03b",  # 导入 + 预处理
            "cp_04", "cp_04c",  # 挑选 + 检查
            "cp_05",  # 提取
            "cp_06", "cp_06b",  # 2D分类 + 筛选
        ],
        "skip_steps": [],
    }

    # 如果用户选择了 3D 重建
    if st.session_state.get("wizard_include_3d", False):
        workflow["steps"].extend(["cp_07", "cp_08", "cp_09"])

    # 调用 workflow 生成器
    try:
        workflow_json = generate_cryosparc_workflow(
            workflow=workflow,
            params=params,
            workflow_name="StructPilot_Beginner_Workflow",
            software="cryosparc",
        )

        if not workflow_json:
            st.error("Workflow 生成失败，请检查参数。")
            return

        json_str = workflow_to_json_str(workflow_json, indent=2)

        st.success("✅ Workflow 生成成功！")
        st.markdown("### 📥 下载 Workflow JSON")
        st.download_button(
            label="⬇️ 下载 workflow.json",
            data=json_str,
            file_name="structpilot_workflow.json",
            mime="application/json",
            use_container_width=True,
        )

        st.markdown("### 📖 导入步骤")
        st.markdown(
            """
            1. 登录 cryoSPARC Web 界面
            2. 进入 Projects 页面，选择目标 Project
            3. 点击 **Import Workflow** 按钮
            4. 上传刚下载的 `structpilot_workflow.json`
            5. 填写必需的文件路径参数（如 blob_paths）
            6. 点击 **Apply to Workspace** → **Queue Job**
            """
        )

        # 重置向导
        if st.button("🔄 重新填写", key="reset_wizard"):
            st.session_state.wizard_step = 0
            st.session_state.wizard_params = {}
            st.rerun()

    except Exception as e:
        st.error(f"生成 Workflow 时出错：{e}")


        # 导航按钮
        col_prev, col_next, col_export = st.columns([1, 1, 1])

        with col_prev:
            if current_step > 0:
                prev_clicked = st.form_submit_button("⬅️ 上一步", use_container_width=True)
            else:
                prev_clicked = False

        with col_next:
            if current_step < total_steps - 1:
                next_clicked = st.form_submit_button("下一步 ➡️", type="primary", use_container_width=True)
            else:
                next_clicked = False

        with col_export:
            if current_step == total_steps - 1:
                export_clicked = st.form_submit_button("🚀 生成 Workflow", type="primary", use_container_width=True)
            else:
                export_clicked = False

    # 处理导航
    if prev_clicked:
        st.session_state.wizard_step = max(0, current_step - 1)
        st.rerun()

    if next_clicked:
        # 验证当前步骤必填参数
        if _validate_step(current_step, st.session_state.wizard_params):
            st.session_state.wizard_step = min(total_steps - 1, current_step + 1)
            st.rerun()
        else:
            st.error("❌ 请填写所有必填参数")

    if export_clicked:
        # 生成 workflow JSON
        _export_workflow(st.session_state.wizard_params, state, app)


def _render_job_params(job_id: str, params_dict: Dict[str, Any]) -> None:
    """渲染单个 job 的参数表单。"""
    param_configs = _JOB_PARAMS_CONFIG.get(job_id, [])
    if not param_configs:
        st.info(f"📋 {job_id} 无需手动配置参数（使用默认值）")
        return

    # 分组：核心参数（展开）和固定参数（折叠）
    key_params = [p for p in param_configs if p.get("flagged", False) and not p.get("locked", False)]
    locked_params = [p for p in param_configs if p.get("locked", False)]

    # 渲染核心参数
    if key_params:
        st.markdown("**🔥 核心参数**")
        for param in key_params:
            _render_param_input(param, params_dict)

    # 渲染固定参数（折叠）
    if locked_params:
        with st.expander("🔒 固定参数（通常无需修改）", expanded=False):
            for param in locked_params:
                _render_param_input(param, params_dict, disabled=True)


def _render_param_input(param: Dict[str, Any], params_dict: Dict[str, Any], disabled: bool = False) -> None:
    """渲染单个参数输入控件。"""
    key = param["key"]
    label = param["label"]
    param_type = param["type"]
    default_value = param.get("default")
    help_text = param.get("help", "")

    # 从 params_dict 读取已有值
    current_value = params_dict.get(key, default_value)

    if param_type == "text":
        value = st.text_input(
            label,
            value=current_value or "",
            placeholder=param.get("placeholder", ""),
            help=help_text,
            key=f"param_{key}",
            disabled=disabled,
        )
        params_dict[key] = value

    elif param_type == "number":
        if "options" in param:
            # 下拉选择
            options = param["options"]
            index = options.index(current_value) if current_value in options else 0
            value = st.selectbox(
                label,
                options=options,
                index=index,
                help=help_text,
                key=f"param_{key}",
                disabled=disabled,
            )
        else:
            # 数字输入
            value = st.number_input(
                label,
                value=float(current_value) if current_value is not None else float(default_value or 0),
                min_value=float(param.get("min", 0)),
                max_value=float(param.get("max", 1000)),
                step=float(param.get("step", 1)),
                help=help_text,
                key=f"param_{key}",
                disabled=disabled,
            )
        params_dict[key] = value


def _validate_step(step_idx: int, params_dict: Dict[str, Any]) -> bool:
    """验证当前步骤的必填参数是否已填写。"""
    step_config = _WIZARD_STEPS[step_idx]
    for job_id in step_config["jobs"]:
        param_configs = _JOB_PARAMS_CONFIG.get(job_id, [])
        for param in param_configs:
            if param.get("required", False):
                key = param["key"]
                value = params_dict.get(key)
                if not value:  # 空字符串或 None
                    return False
    return True


def _export_workflow(params_dict: Dict[str, Any], state: Any, app: Any) -> None:
    """生成并导出 workflow JSON。"""
    # 构建 workflow 结构（所有步骤）
    workflow = {
        "steps": ["cp_01", "cp_02", "cp_03", "cp_03b", "cp_04", "cp_04c", "cp_05", "cp_06", "cp_06b"],
        "skip_steps": [],
    }

    # 调用生成器
    workflow_json = generate_cryosparc_workflow(
        workflow=workflow,
        params=params_dict,
        workflow_name=f"StructPilot_Beginner_{params_dict.get('pixel_size', '0.0')}A",
        software="cryosparc",
    )

    if workflow_json:
        json_str = workflow_to_json_str(workflow_json, indent=2)

        st.success("✅ Workflow 生成成功！")
        st.markdown("### 📥 下载 Workflow JSON")
        st.download_button(
            label="⬇️ 下载 workflow.json",
            data=json_str,
            file_name="structpilot_workflow.json",
            mime="application/json",
            use_container_width=True,
        )

        with st.expander("📄 预览 JSON（点击展开）"):
            st.code(json_str, language="json")

        st.info(
            "💡 **下一步操作**：\n"
            "1. 下载此文件到本地\n"
            "2. 在 cryoSPARC Web界面中，点击 Workflows → Import\n"
            "3. 上传此 JSON 文件\n"
            "4. 修改第一步的文件路径（blob_paths），然后运行！"
        )
    else:
        st.error("❌ Workflow 生成失败，请检查参数配置。")
