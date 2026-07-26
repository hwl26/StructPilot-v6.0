"""CryoSPARC Workflow参数配置界面

特点：
1. 参考cryoSPARC UI设计，卡片式参数分组
2. 左右分栏：左侧参数编辑区 + 右侧流程图
3. 参数分类：必填参数 Tab + 高级参数 Tab
4. 智能关联：蛋白直径自动计算box size和mask diameter
"""

from __future__ import annotations
import json
import streamlit as st
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import math

# 参数显示名称映射（中英文对照）
PARAM_LABELS = {
    "blob_paths": "数据路径",
    "psize_A": "像素大小 (Å/pix)",
    "accel_kv": "加速电压 (kV)",
    "cs_mm": "球差系数 (mm)",
    "total_dose_e_per_A2": "总剂量 (e/Å²)",
    "max_num_hits": "最大颗粒数",
    "diameter": "颗粒直径最小值 (Å)",
    "diameter_max": "颗粒直径最大值 (Å)",
    "min_distance": "最小间距比例",
    "box_size_pix": "提取框大小 (pix)",
    "bin_size_pix": "降采样大小 (pix)",
    "class2D_K": "2D分类类别数",
    "class2D_max_res": "最大分辨率 (Å)",
    "class2D_window_inner_A": "圆形遮罩直径 (Å)",
    "class2D_num_full_iter_batch": "迭代轮数",
    "compute_num_gpus": "GPU数量",
    "compute_use_ssd": "使用SSD缓存",
}

# 参数占位符提示
PARAM_PLACEHOLDERS = {
    "blob_paths": "例如: /data/project/Movies/*.mrc",
    "psize_A": "根据采集条件填写，如 0.96",
    "accel_kv": "通常为 300 或 200",
    "cs_mm": "根据显微镜型号填写，如 2.7",
    "total_dose_e_per_A2": "根据采集方案填写，通常 40-60",
    "diameter": "根据蛋白大小估算 (Å)",
    "diameter_max": "通常与最小值相同或略大",
}

# 必填参数列表（显示在"必填参数"Tab）
REQUIRED_PARAMS = {
    "J1": ["blob_paths", "psize_A", "accel_kv", "cs_mm", "total_dose_e_per_A2"],
    "J4": ["diameter", "diameter_max"],
    "J5": ["box_size_pix"],
    "J6": ["class2D_window_inner_A"],
}

# 高级参数列表（显示在"高级参数"Tab，默认折叠）
ADVANCED_PARAMS = {
    "J4": ["max_num_hits", "min_distance"],
    "J5": ["bin_size_pix", "compute_num_gpus"],
    "J6": ["class2D_K", "class2D_max_res", "class2D_num_full_iter_batch", "compute_num_gpus", "compute_use_ssd"],
}

# Job类型显示名称
JOB_LABELS = {
    "import_micrographs": "导入显微照片",
    "patch_ctf_estimation_multi": "CTF估计",
    "curate_exposures_v2": "曝光筛选",
    "blob_picker_gpu": "自动挑粒子",
    "extract_micrographs_multi": "提取颗粒",
    "class_2D_new": "2D分类",
    "select_2D": "人工筛选2D类",
}


def calculate_box_size(protein_diameter_A: float, pixel_size: float) -> int:
    """根据蛋白直径自动计算提取框大小

    公式: box_size = protein_diameter / 0.9 / pixel_size * (1.5~2)
    取1.75倍作为默认值
    """
    if protein_diameter_A <= 0 or pixel_size <= 0:
        return 0

    box_size = (protein_diameter_A / 0.9 / pixel_size) * 1.75
    # 取最近的偶数
    return int(math.ceil(box_size / 2) * 2)


def calculate_mask_diameter(protein_diameter_A: float) -> int:
    """根据蛋白直径自动计算圆形遮罩直径

    公式: mask_diameter = protein_diameter / 0.9
    """
    if protein_diameter_A <= 0:
        return 0

    return int(math.ceil(protein_diameter_A / 0.9))


def generate_workflow_diagram(workflow_data: Dict[str, Any]) -> str:
    """生成Mermaid流程图代码"""
    jobs = workflow_data.get("jobs", {})

    # 构建节点定义
    nodes = []
    edges = []

    for job_id in sorted(jobs.keys()):
        job = jobs[job_id]
        job_type = job.get("jobType", "")
        label = JOB_LABELS.get(job_type, job_type)

        # 节点样式：圆角矩形
        nodes.append(f'    {job_id}["{job_id}<br/>{label}"]')

        # 解析依赖关系（从groups中提取）
        groups = job.get("groups", [])
        for group in groups:
            if len(group) >= 2:
                source_job = group[0].split(".")[0]  # 提取Job ID
                edges.append(f'    {source_job} --> {job_id}')

    # 生成Mermaid图
    mermaid_code = "graph TD\n" + "\n".join(nodes) + "\n" + "\n".join(edges)

    return mermaid_code


def render_parameter_card(
    job_id: str,
    param_key: str,
    param_data: Dict[str, Any],
    pixel_size: float = 0.96,
    protein_diameter: Optional[float] = None
) -> Any:
    """渲染单个参数卡片

    Args:
        job_id: Job ID (如 J1, J4)
        param_key: 参数键名
        param_data: 参数数据字典（包含value, locked等）
        pixel_size: 像素大小（用于自动计算）
        protein_diameter: 蛋白直径（用于自动计算）

    Returns:
        用户输入的参数值
    """
    label = PARAM_LABELS.get(param_key, param_key)
    placeholder = PARAM_PLACEHOLDERS.get(param_key, "")
    default_value = param_data.get("value", "")

    # 检查是否是自动计算参数
    auto_calculated = False
    if param_key == "box_size_pix" and protein_diameter and protein_diameter > 0:
        calculated_value = calculate_box_size(protein_diameter, pixel_size)
        st.info(f"💡 **自动计算**: {label} = {calculated_value} pix")
        st.caption(f"根据蛋白直径 {protein_diameter:.0f} Å 自动计算")
        return calculated_value

    if param_key == "class2D_window_inner_A" and protein_diameter and protein_diameter > 0:
        calculated_value = calculate_mask_diameter(protein_diameter)
        st.info(f"💡 **自动计算**: {label} = {calculated_value} Å")
        st.caption(f"根据蛋白直径 {protein_diameter:.0f} Å 自动计算")
        return calculated_value

    # 根据参数类型渲染输入组件
    unique_key = f"{job_id}_{param_key}"

    if isinstance(default_value, bool):
        return st.checkbox(label, value=default_value, key=unique_key)

    elif isinstance(default_value, (int, float)):
        # 数字类型：使用number_input
        if isinstance(default_value, int):
            return st.number_input(
                label,
                value=default_value,
                step=1,
                key=unique_key,
                help=placeholder
            )
        else:
            return st.number_input(
                label,
                value=default_value,
                step=0.1,
                format="%.2f",
                key=unique_key,
                help=placeholder
            )

    elif isinstance(default_value, str):
        # 字符串类型：使用text_input
        return st.text_input(
            label,
            value=default_value,
            placeholder=placeholder,
            key=unique_key
        )

    else:
        # 未知类型：使用text_input
        return st.text_input(
            label,
            value=str(default_value),
            placeholder=placeholder,
            key=unique_key
        )


def render_workflow_config(workflow_path: Path) -> Dict[str, Any]:
    """渲染Workflow参数配置界面

    Args:
        workflow_path: workflow JSON文件路径

    Returns:
        用户配置的参数字典
    """
    # 加载workflow数据
    if not workflow_path.exists():
        st.error(f"❌ 找不到workflow文件: {workflow_path}")
        return {}

    try:
        workflow_data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"❌ 解析workflow文件失败: {e}")
        return {}

    jobs = workflow_data.get("jobs", {})
    if not jobs:
        st.warning("⚠️ Workflow中没有任务")
        return {}

    # === 左右分栏布局 ===
    left_col, right_col = st.columns([6, 4])

    # === 右侧：流程图 ===
    with right_col:
        st.markdown("### 📊 Workflow流程图")
        mermaid_code = generate_workflow_diagram(workflow_data)
        st.markdown(f"""
        ```mermaid
        {mermaid_code}
        ```
        """)
        st.caption("📌 流程自动解析自workflow配置")

    # === 左侧：参数配置 ===
    with left_col:
        st.markdown("### ⚙️ 参数配置")

        # 获取像素大小和蛋白直径（用于自动计算）
        pixel_size = jobs.get("J1", {}).get("parameters", {}).get("psize_A", {}).get("value", 0.96)
        protein_diameter = None  # 稍后从用户输入获取

        # === Tab分组：必填参数 + 高级参数 ===
        tab_required, tab_advanced = st.tabs(["📝 必填参数", "🔧 高级参数（可选）"])

        user_params = {}

        # === 必填参数Tab ===
        with tab_required:
            st.caption("请填写以下必填参数，带 * 的参数需要根据课题组/蛋白情况填写")

            for job_id in sorted(jobs.keys()):
                if job_id not in REQUIRED_PARAMS:
                    continue

                job = jobs[job_id]
                job_type = job.get("jobType", "")
                job_label = JOB_LABELS.get(job_type, job_type)
                parameters = job.get("parameters", {})

                # 渲染Job卡片
                with st.expander(f"**{job_id}**: {job_label}", expanded=True):
                    for param_key in REQUIRED_PARAMS[job_id]:
                        if param_key not in parameters:
                            continue

                        param_data = parameters[param_key]

                        # 特殊处理：蛋白直径参数
                        if param_key == "diameter":
                            protein_diameter = render_parameter_card(
                                job_id, param_key, param_data, pixel_size
                            )
                            user_params[f"{job_id}.{param_key}"] = protein_diameter
                        else:
                            value = render_parameter_card(
                                job_id, param_key, param_data, pixel_size, protein_diameter
                            )
                            user_params[f"{job_id}.{param_key}"] = value

        # === 高级参数Tab ===
        with tab_advanced:
            st.caption("以下参数已预设推荐值，一般情况下无需修改")

            for job_id in sorted(jobs.keys()):
                if job_id not in ADVANCED_PARAMS:
                    continue

                job = jobs[job_id]
                job_type = job.get("jobType", "")
                job_label = JOB_LABELS.get(job_type, job_type)
                parameters = job.get("parameters", {})

                # 渲染Job卡片（默认折叠）
                with st.expander(f"**{job_id}**: {job_label}", expanded=False):
                    for param_key in ADVANCED_PARAMS[job_id]:
                        if param_key not in parameters:
                            continue

                        param_data = parameters[param_key]
                        value = render_parameter_card(
                            job_id, param_key, param_data, pixel_size, protein_diameter
                        )
                        user_params[f"{job_id}.{param_key}"] = value

    return user_params


def save_workflow_config(user_params: Dict[str, Any], output_path: Path) -> bool:
    """保存用户配置的参数到JSON文件

    Args:
        user_params: 用户配置的参数字典
        output_path: 输出文件路径

    Returns:
        是否保存成功
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(user_params, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
        return False


# ============================================================================
# 测试代码（直接运行此文件查看效果）
# ============================================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Workflow配置", layout="wide")

    st.title("🔬 CryoSPARC Workflow 参数配置")
    st.markdown("---")

    # 测试用workflow文件路径
    workflow_path = Path("2d-classfication_zxl.json")

    if workflow_path.exists():
        user_params = render_workflow_config(workflow_path)

        st.markdown("---")
        st.markdown("### 📋 配置预览")
        st.json(user_params)

        if st.button("💾 保存配置", type="primary"):
            output_path = Path("workflow_config_output.json")
            if save_workflow_config(user_params, output_path):
                st.success(f"✅ 配置已保存到 {output_path}")
    else:
        st.error(f"❌ 找不到测试文件: {workflow_path}")
        st.info("💡 请将 `2d-classfication_zxl.json` 放在同目录下")
