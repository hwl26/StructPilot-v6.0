"""Interactive CryoSPARC workflow parameter editor.

The editor keeps a real CryoSPARC workflow template intact.  Users edit a
copy of the template's job parameters; exporting later preserves the original
``jobs`` and ``groups`` topology so the resulting JSON remains importable.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import streamlit as st


PARAM_LABELS = {
    "blob_paths": "数据路径",
    "gainref_path": "Gain reference 文件",
    "psize_A": "像素大小",
    "accel_kv": "加速电压",
    "cs_mm": "球差系数",
    "total_dose_e_per_A2": "总剂量",
    "compute_num_gpus": "GPU 数量",
    "bfactor": "B-factor",
    "max_num_hits": "最大挑选颗粒数",
    "diameter": "颗粒直径下限",
    "diameter_max": "颗粒直径上限",
    "min_distance": "最小间距比例",
    "box_size_pix": "提取 box size",
    "bin_size_pix": "降采样 box size",
    "class2D_K": "2D 类别数",
    "class2D_max_res": "2D 最大分辨率",
    "class2D_window_inner_A": "2D 圆形遮罩直径",
    "class2D_num_full_iter_batch": "2D 完整迭代轮数",
    "compute_use_ssd": "使用 SSD 缓存",
    "update_location": "更新颗粒位置",
    "update_alignments2D": "保留 2D 对齐",
    "recenter_key": "重心参考",
}

PARAM_UNITS = {
    "psize_A": "A/pix",
    "accel_kv": "kV",
    "cs_mm": "mm",
    "total_dose_e_per_A2": "e-/A2",
    "diameter": "A",
    "diameter_max": "A",
    "box_size_pix": "pix",
    "bin_size_pix": "pix",
    "class2D_max_res": "A",
    "class2D_window_inner_A": "A",
}

JOB_LABELS = {
    "import_movies": "Import Movies",
    "import_micrographs": "Import Micrographs",
    "patch_motion_correction_multi": "Patch Motion Correction",
    "patch_ctf_estimation_multi": "Patch CTF Estimation",
    "curate_exposures_v2": "Manually Curate Exposures",
    "blob_picker_gpu": "Blob Picker",
    "template_picker_gpu": "Template Picker",
    "extract_micrographs_multi": "Extract From Micrographs",
    "class_2D_new": "2D Classification",
    "select_2D": "Select 2D Classes",
}

_ACTIVE_JOB_KEY = "cswf_active_job"
_INITIALIZED_KEY = "cswf_initialized_template"
_PENDING_ACTION_KEY = "cswf_pending_action"

# These are starting points only. Applying one never locks a field: every
# resulting value stays in the manual tab for the user to adjust.
COMMON_PRESETS = {
    "300 kV 标准 2D 筛选": {
        "J1": {"accel_kv": 300, "cs_mm": 2.7, "total_dose_e_per_A2": 50},
        "J2": {"compute_num_gpus": 4},
        "J4": {"max_num_hits": 400, "min_distance": 0.6},
        "J5": {"compute_num_gpus": 1},
        "J6": {"class2D_K": 100, "class2D_max_res": 5, "class2D_num_full_iter_batch": 40, "compute_num_gpus": 4},
    },
    "小颗粒保守挑选": {
        "J4": {"max_num_hits": 300, "min_distance": 0.7},
        "J6": {"class2D_K": 150, "class2D_max_res": 6, "class2D_num_full_iter_batch": 50},
    },
    "快速预筛 2D": {
        "J4": {"max_num_hits": 250},
        "J5": {"compute_num_gpus": 1},
        "J6": {"class2D_K": 50, "class2D_max_res": 8, "class2D_num_full_iter_batch": 25, "compute_num_gpus": 1},
    },
}


def _value_key(job_id: str, param_key: str) -> str:
    return f"cswf_value__{job_id}__{param_key}"


def _template_signature(workflow_path: Path, workflow_data: Dict[str, Any]) -> str:
    return f"{workflow_path.resolve()}::{workflow_data.get('_id', '')}::{len(workflow_data.get('jobs', {}))}"


def _job_label(job_id: str, job: Dict[str, Any]) -> str:
    return JOB_LABELS.get(job.get("jobType", ""), job.get("jobType", job_id))


def _iter_parameters(workflow_data: Dict[str, Any]) -> Iterable[tuple[str, str, Dict[str, Any]]]:
    for job_id, job in workflow_data.get("jobs", {}).items():
        for param_key, param_data in job.get("parameters", {}).items():
            if isinstance(param_data, dict):
                yield job_id, param_key, param_data


def _initialise_editor(workflow_path: Path, workflow_data: Dict[str, Any]) -> None:
    signature = _template_signature(workflow_path, workflow_data)
    if st.session_state.get(_INITIALIZED_KEY) != signature:
        for job_id, param_key, param_data in _iter_parameters(workflow_data):
            st.session_state[_value_key(job_id, param_key)] = param_data.get("value")
        job_ids = list(workflow_data.get("jobs", {}))
        st.session_state[_ACTIVE_JOB_KEY] = job_ids[0] if job_ids else ""
        st.session_state[_INITIALIZED_KEY] = signature

    _apply_pending_action(workflow_data)


def _apply_pending_action(workflow_data: Dict[str, Any]) -> None:
    """Apply presets before the associated Streamlit widgets are created."""
    action = st.session_state.pop(_PENDING_ACTION_KEY, None)
    if not action:
        return

    kind = action.get("kind")
    if kind == "reset":
        for job_id, param_key, param_data in _iter_parameters(workflow_data):
            st.session_state[_value_key(job_id, param_key)] = param_data.get("value")
        return

    if kind != "preset":
        return

    preset = COMMON_PRESETS.get(action.get("name"), {})
    for job_id, values in preset.items():
        job_params = workflow_data.get("jobs", {}).get(job_id, {}).get("parameters", {})
        for param_key, value in values.items():
            if param_key in job_params:
                st.session_state[_value_key(job_id, param_key)] = value


def _suggested_value(param_key: str, values: Dict[str, Dict[str, Any]]) -> Optional[Any]:
    """Return an optional, never-forced suggestion derived from entered data."""
    import_job = values.get("J1", {})
    picker_job = values.get("J4", {})
    pixel_size = import_job.get("psize_A")
    diameter = picker_job.get("diameter")
    if not isinstance(pixel_size, (int, float)) or pixel_size <= 0:
        return None
    if not isinstance(diameter, (int, float)) or diameter <= 0:
        return None
    if param_key == "box_size_pix":
        return int(math.ceil((diameter / pixel_size * 1.75) / 2) * 2)
    if param_key == "class2D_window_inner_A":
        return int(math.ceil(diameter / 0.9))
    return None


def _read_values(workflow_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    values: Dict[str, Dict[str, Any]] = {}
    for job_id, param_key, param_data in _iter_parameters(workflow_data):
        values.setdefault(job_id, {})[param_key] = st.session_state.get(
            _value_key(job_id, param_key), param_data.get("value")
        )
    return values


def _render_parameter_input(
    job_id: str,
    param_key: str,
    param_data: Dict[str, Any],
    values: Dict[str, Dict[str, Any]],
) -> None:
    value = st.session_state.get(_value_key(job_id, param_key), param_data.get("value"))
    label = PARAM_LABELS.get(param_key, param_key.replace("_", " "))
    unit = PARAM_UNITS.get(param_key)
    if unit:
        label = f"{label} ({unit})"
    key = _value_key(job_id, param_key)

    if isinstance(value, bool):
        st.checkbox(label, value=value, key=key)
    elif isinstance(value, int) and not isinstance(value, bool):
        st.number_input(label, value=value, step=1, key=key)
    elif isinstance(value, float):
        st.number_input(label, value=value, step=0.1, format="%.3f", key=key)
    else:
        st.text_input(label, value="" if value is None else str(value), key=key)

    suggestion = _suggested_value(param_key, values)
    if suggestion is not None and suggestion != value:
        st.caption(f"建议值: {suggestion}。这是可选建议，仍可直接填写任意适用数值。")


def _job_levels(jobs: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Assign columns from workflow groups so branches remain legible."""
    levels: Dict[str, int] = {}

    def level_for(job_id: str, visiting: set[str]) -> int:
        if job_id in levels:
            return levels[job_id]
        if job_id in visiting:
            return 0
        visiting.add(job_id)
        sources = []
        for group in jobs.get(job_id, {}).get("groups", []):
            if group and isinstance(group[0], str) and "." in group[0]:
                source = group[0].split(".", 1)[0]
                if source in jobs:
                    sources.append(level_for(source, visiting))
        visiting.discard(job_id)
        levels[job_id] = max(sources, default=-1) + 1
        return levels[job_id]

    for job_id in jobs:
        level_for(job_id, set())
    return levels


def _render_interactive_workflow(workflow_data: Dict[str, Any], active_job: str) -> None:
    jobs = workflow_data.get("jobs", {})
    levels = _job_levels(jobs)
    max_level = max(levels.values(), default=0)

    st.markdown("#### Workflow")
    st.caption("点击任一节点，即可打开左侧对应的参数卡。蓝色节点为当前编辑位置。")
    st.markdown("<div class='cswf-canvas'>", unsafe_allow_html=True)
    for level in range(max_level + 1):
        current = [job_id for job_id in jobs if levels.get(job_id) == level]
        if not current:
            continue
        columns = st.columns(len(current))
        for col, job_id in zip(columns, current):
            job = jobs[job_id]
            with col:
                title = _job_label(job_id, job)
                is_active = job_id == active_job
                if st.button(
                    f"{job_id}  {title}",
                    key=f"cswf_node_{job_id}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[_ACTIVE_JOB_KEY] = job_id
                    st.rerun()
                sources = []
                for group in job.get("groups", []):
                    if group and isinstance(group[0], str) and "." in group[0]:
                        sources.append(group[0].split(".", 1)[0])
                if sources:
                    st.caption("来自 " + " / ".join(sources))
        if level < max_level:
            st.markdown("<div class='cswf-connector'>↓</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _canonical_parameters(values: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Keep existing downstream workflow generation APIs populated."""
    j1, j4 = values.get("J1", {}), values.get("J4", {})
    j5, j6 = values.get("J5", {}), values.get("J6", {})
    return {
        "movies_path": j1.get("blob_paths", ""),
        "micrographs_path": j1.get("blob_paths", ""),
        "pixel_size": j1.get("psize_A"),
        "voltage": j1.get("accel_kv"),
        "Cs": j1.get("cs_mm"),
        "total_dose": j1.get("total_dose_e_per_A2"),
        "particle_diameter": j4.get("diameter"),
        "particle_diameter_max": j4.get("diameter_max"),
        "max_num_hits": j4.get("max_num_hits"),
        "box_size": j5.get("box_size_pix"),
        "bin_size": j5.get("bin_size_pix"),
        "class2d_num_classes": j6.get("class2D_K"),
        "class2d_gpus": j6.get("compute_num_gpus"),
    }


def render_workflow_config(workflow_path: Path) -> Optional[Dict[str, Any]]:
    """Render editable cards and return an export-ready configuration on confirm.

    ``None`` means the user is still editing.  A returned value carries both
    conventional StructPilot parameter names and the full CryoSPARC template
    plus per-job overrides for exact JSON export.
    """
    try:
        workflow_data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"无法读取 workflow 模板: {exc}")
        return None

    jobs = workflow_data.get("jobs", {})
    if not isinstance(jobs, dict) or not jobs:
        st.error("workflow 模板不包含 jobs，无法生成可导入文件。")
        return None

    _initialise_editor(workflow_path, workflow_data)
    active_job = st.session_state.get(_ACTIVE_JOB_KEY)
    if active_job not in jobs:
        active_job = next(iter(jobs))
        st.session_state[_ACTIVE_JOB_KEY] = active_job

    st.markdown(
        """
        <style>
        .cswf-head { margin: 0.2rem 0 0.45rem; }
        .cswf-head h2 { margin: 0; font-size: 1.45rem !important; }
        .cswf-panel { border: 1px solid #d8e1ea; background: #ffffff; padding: 0.7rem; }
        .cswf-node-caption { color: #64748b; font-size: 0.78rem; }
        .cswf-connector { text-align: center; color: #94a3b8; line-height: 1.1; font-size: 1.15rem; }
        .cswf-canvas { border: 1px solid #d8e1ea; background-color: #fbfdff;
            background-image: radial-gradient(#dbe5ee 1px, transparent 1px); background-size: 14px 14px;
            padding: 0.75rem; min-height: 540px; }
        </style>
        <div class='cswf-head'><h2>🎯 cryoSPARC Workflow 参数填写</h2></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("基于可导入的 2D 分类模板编辑。所有参数均可修改；确认后会保留 Job 与数据连接结构。")

    left_col, right_col = st.columns([0.9, 1.7], gap="large")
    with left_col:
        st.markdown("#### 参数卡")
        job_columns = st.columns(2)
        for index, (job_id, job) in enumerate(jobs.items()):
            with job_columns[index % 2]:
                if st.button(
                    job_id,
                    key=f"cswf_card_selector_{job_id}",
                    type="primary" if job_id == active_job else "secondary",
                    use_container_width=True,
                    help=_job_label(job_id, job),
                ):
                    st.session_state[_ACTIVE_JOB_KEY] = job_id
                    st.rerun()

        manual_tab, common_tab = st.tabs(["手动填写", "常用值"])
        with manual_tab:
            job = jobs[active_job]
            st.markdown(f"##### {active_job} · {_job_label(active_job, job)}")
            st.caption("所有字段均可编辑。选中其他 Job 或点击右侧节点可切换参数卡。")
            values = _read_values(workflow_data)
            parameters = job.get("parameters", {})
            if not parameters:
                st.info("该 Job 不需要填写参数，可通过右侧节点继续检查后续步骤。")
            else:
                for param_key, param_data in parameters.items():
                    _render_parameter_input(active_job, param_key, param_data, values)

        with common_tab:
            st.caption("常用值只会预填模板，应用后仍可在“手动填写”中继续修改。")
            for preset_name, preset_values in COMMON_PRESETS.items():
                affected_jobs = [job_id for job_id in preset_values if job_id in jobs]
                if not affected_jobs:
                    continue
                st.markdown(f"**{preset_name}**")
                st.caption("影响 " + "、".join(affected_jobs))
                if st.button("应用", key=f"cswf_apply_{preset_name}", use_container_width=True):
                    st.session_state[_PENDING_ACTION_KEY] = {"kind": "preset", "name": preset_name}
                    st.rerun()
            st.divider()
            if st.button("恢复模板默认值", key="cswf_reset", use_container_width=True):
                st.session_state[_PENDING_ACTION_KEY] = {"kind": "reset"}
                st.rerun()

        st.divider()
        confirmed = st.button("确认参数并生成 Workflow", key="cswf_confirm", type="primary", use_container_width=True)

    with right_col:
        _render_interactive_workflow(workflow_data, active_job)

    if not confirmed:
        return None

    values = _read_values(workflow_data)
    result = _canonical_parameters(values)
    result["_workflow_template"] = copy.deepcopy(workflow_data)
    result["_workflow_values"] = values
    return result


def save_workflow_config(user_params: Dict[str, Any], output_path: Path) -> bool:
    """Save editor state for recovery; final imports use the workflow generator."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(user_params, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError as exc:
        st.error(f"保存失败: {exc}")
        return False
