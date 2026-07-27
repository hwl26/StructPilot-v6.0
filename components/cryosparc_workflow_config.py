"""Interactive CryoSPARC workflow parameter editor.

The editor keeps a real CryoSPARC workflow template intact.  Users edit a
copy of the template's job parameters; exporting later preserves the original
``jobs`` and ``groups`` topology so the resulting JSON remains importable.
"""

from __future__ import annotations

import copy
import html
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
    "box_size_pix": "Extraction box size",
    "bin_size_pix": "降采样 box size",
    "class2D_K": "2D 类别数",
    "class2D_max_res": "2D 最大分辨率",
    "class2D_window_inner_A": "Circular mask diameter",
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

JOB_PHASE_LABELS = {
    "import_movies": "IMPORT",
    "import_micrographs": "IMPORT",
    "patch_motion_correction_multi": "PREPROCESS",
    "patch_ctf_estimation_multi": "PREPROCESS",
    "curate_exposures_v2": "CURATE",
    "blob_picker_gpu": "PICK",
    "template_picker_gpu": "PICK",
    "extract_micrographs_multi": "EXTRACT",
    "class_2D_new": "CLASSIFY",
    "select_2D": "SELECT",
}

_ACTIVE_JOB_KEY = "cswf_active_job"
_INITIALIZED_KEY = "cswf_initialized_template"
_PENDING_ACTION_KEY = "cswf_pending_action"
_VALUES_STORE_KEY = "cswf_values_store"
_AUTO_DERIVE_KEY = "cswf_auto_derive"
_QUICK_READY_KEY = "cswf_quick_ready"
_QUICK_DIAMETER_KEY = "cswf_quick_diameter_A"
_QUICK_PATH_KEY = "cswf_quick_blob_paths"
_QUICK_GPU_KEY = "cswf_quick_gpu_count"
_QUICK_DIAMETER_INPUT_KEY = "cswf_quick_diameter_A_input"
_QUICK_PATH_INPUT_KEY = "cswf_quick_blob_paths_input"
_QUICK_GPU_INPUT_KEY = "cswf_quick_gpu_count_input"
_EDITOR_STATE_VERSION = 4

DEFAULT_PIXEL_SIZE_A = 0.96
MASK_FILL_RATIO = 0.9
BOX_SIZE_SCALE = 2.0
BOX_SIZE_ALIGNMENT = 16
MIN_BOX_PADDING_RATIO = 1.5
MAX_GPU_COUNT = 64
MAX_PATH_LENGTH = 2048

# CryoSPARC workflow exports do not carry a reliable ``required`` flag.  This
# small schema layer identifies values that depend on the user's experiment;
# every other exported parameter remains an editable recommended value.
REQUIRED_PARAMS_BY_JOB_TYPE = {
    "import_movies": {"blob_paths"},
    "import_micrographs": {"blob_paths"},
    "blob_picker_gpu": {"diameter"},
    "template_picker_gpu": {"diameter"},
}

DERIVED_PARAM_KEYS = {"box_size_pix", "class2D_window_inner_A"}

REQUIRED_PLACEHOLDERS = {
    "blob_paths": "根据课题组数据路径填写，例如 /project/data/*.mrc",
    "diameter": "根据蛋白实际直径填写，例如 120",
}

def _value_key(job_id: str, param_key: str) -> str:
    return f"cswf_value__{job_id}__{param_key}"


def _template_signature(
    workflow_path: Path,
    workflow_data: Dict[str, Any],
    initial_params: Optional[Dict[str, Any]] = None,
) -> str:
    initial_signature = json.dumps(initial_params or {}, ensure_ascii=False, sort_keys=True, default=str)
    return (
        f"{workflow_path.resolve()}::{workflow_data.get('_id', '')}::"
        f"{len(workflow_data.get('jobs', {}))}::v{_EDITOR_STATE_VERSION}::{initial_signature}"
    )


def _job_label(job_id: str, job: Dict[str, Any]) -> str:
    return JOB_LABELS.get(job.get("jobType", ""), job.get("jobType", job_id))


def _job_sources(job: Dict[str, Any], jobs: Dict[str, Dict[str, Any]]) -> list[str]:
    """Return unique upstream Job IDs in template order."""
    sources: list[str] = []
    for group in job.get("groups", []):
        if not group or not isinstance(group[0], str) or "." not in group[0]:
            continue
        source = group[0].split(".", 1)[0]
        if source in jobs and source not in sources:
            sources.append(source)
    return sources


def _iter_parameters(workflow_data: Dict[str, Any]) -> Iterable[tuple[str, str, Dict[str, Any]]]:
    for job_id, job in workflow_data.get("jobs", {}).items():
        for param_key, param_data in job.get("parameters", {}).items():
            if isinstance(param_data, dict):
                yield job_id, param_key, param_data


def _template_validation_errors(workflow_data: Any) -> list[str]:
    """Validate the minimum CryoSPARC workflow contract before rendering."""
    if not isinstance(workflow_data, dict):
        return ["workflow 模板顶层必须是 JSON 对象。"]
    jobs = workflow_data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return ["workflow 模板不包含有效的 jobs。"]

    errors: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job_id, str) or not isinstance(job, dict):
            errors.append("workflow 中存在无效的 Job 定义。")
            continue
        if not isinstance(job.get("jobType"), str) or not job.get("jobType"):
            errors.append(f"{job_id} 缺少有效的 jobType。")
        groups = job.get("groups")
        if not isinstance(groups, list):
            errors.append(f"{job_id} 的 groups 必须是列表。")
        else:
            for group in groups:
                if not isinstance(group, list) or len(group) != 2:
                    errors.append(f"{job_id} 包含无效的数据连接。")
                    continue
                source = group[0]
                if not isinstance(source, str) or "." not in source:
                    errors.append(f"{job_id} 包含无效的数据来源。")
                    continue
                if source.split(".", 1)[0] not in jobs:
                    errors.append(f"{job_id} 引用了不存在的上游 Job。")
        parameters = job.get("parameters")
        if not isinstance(parameters, dict):
            errors.append(f"{job_id} 的 parameters 必须是对象。")
            continue
        for param_key, param_data in parameters.items():
            if not isinstance(param_key, str) or not isinstance(param_data, dict):
                errors.append(f"{job_id} 包含无效的参数定义。")
            elif "value" not in param_data:
                errors.append(f"{job_id}.{param_key} 缺少 value 字段。")
    return errors


def _is_required_parameter(job: Dict[str, Any], param_key: str) -> bool:
    return param_key in REQUIRED_PARAMS_BY_JOB_TYPE.get(job.get("jobType", ""), set())


def _partition_parameters(
    job: Dict[str, Any],
) -> tuple[list[tuple[str, Dict[str, Any]]], list[tuple[str, Dict[str, Any]]]]:
    required: list[tuple[str, Dict[str, Any]]] = []
    recommended: list[tuple[str, Dict[str, Any]]] = []
    for param_key, param_data in job.get("parameters", {}).items():
        target = required if _is_required_parameter(job, param_key) else recommended
        target.append((param_key, param_data))
    return required, recommended


def _empty_required_value(param_data: Dict[str, Any]) -> Any:
    return "" if isinstance(param_data.get("value"), str) else None


def _starting_value(
    workflow_data: Dict[str, Any],
    overrides: Dict[str, Dict[str, Any]],
    job_id: str,
    param_key: str,
    param_data: Dict[str, Any],
) -> Any:
    if param_key in overrides.get(job_id, {}):
        return overrides[job_id][param_key]
    job = workflow_data.get("jobs", {}).get(job_id, {})
    if _is_required_parameter(job, param_key):
        return _empty_required_value(param_data)
    return param_data.get("value")


def _initial_overrides(initial_params: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map edited onboarding values onto their real CryoSPARC job fields."""
    params = initial_params or {}
    overrides: Dict[str, Dict[str, Any]] = {}

    def set_value(job_ids, key, source_key):
        value = params.get(source_key)
        if value is None:
            return
        for job_id in job_ids:
            overrides.setdefault(job_id, {})[key] = value

    set_value(["J1"], "blob_paths", "micrographs_path")
    if not overrides.get("J1", {}).get("blob_paths"):
        set_value(["J1"], "blob_paths", "movies_path")
    set_value(["J1"], "psize_A", "pixel_size")
    set_value(["J1"], "accel_kv", "voltage")
    set_value(["J1"], "cs_mm", "Cs")
    set_value(["J1"], "total_dose_e_per_A2", "total_dose")
    set_value(["J4"], "diameter", "particle_diameter")
    set_value(["J4"], "diameter_max", "particle_diameter_max")
    if "particle_diameter_max" not in params:
        set_value(["J4"], "diameter_max", "particle_diameter")
    set_value(["J5", "J8"], "box_size_pix", "box_size")
    set_value(["J6", "J9"], "class2D_K", "num_classes_2d")
    if "num_classes_2d" not in params:
        set_value(["J6", "J9"], "class2D_K", "class2d_num_classes")
    set_value(["J6", "J9"], "class2D_window_inner_A", "mask_diameter")
    set_value(["J2", "J5", "J6", "J8", "J9"], "compute_num_gpus", "gpu_count")
    if "gpu_count" not in params:
        set_value(["J2", "J5", "J6", "J8", "J9"], "compute_num_gpus", "class2d_gpus")
    return overrides


def _initialise_editor(
    workflow_path: Path,
    workflow_data: Dict[str, Any],
    initial_params: Optional[Dict[str, Any]] = None,
) -> None:
    signature = _template_signature(workflow_path, workflow_data, initial_params)
    overrides = _initial_overrides(initial_params)
    if st.session_state.get(_INITIALIZED_KEY) != signature:
        store: Dict[str, Dict[str, Any]] = {}
        for job_id, param_key, param_data in _iter_parameters(workflow_data):
            st.session_state.pop(_value_key(job_id, param_key), None)
            store.setdefault(job_id, {})[param_key] = _starting_value(
                workflow_data, overrides, job_id, param_key, param_data
            )
        st.session_state[_VALUES_STORE_KEY] = store
        job_ids = list(workflow_data.get("jobs", {}))
        st.session_state[_ACTIVE_JOB_KEY] = job_ids[0] if job_ids else ""
        st.session_state[_INITIALIZED_KEY] = signature
        st.session_state.setdefault(_QUICK_READY_KEY, False)
        st.session_state.setdefault(
            _QUICK_DIAMETER_KEY, store.get("J4", {}).get("diameter")
        )
        st.session_state.setdefault(
            _QUICK_PATH_KEY, store.get("J1", {}).get("blob_paths") or ""
        )
        st.session_state.setdefault(
            _QUICK_GPU_KEY, store.get("J2", {}).get("compute_num_gpus") or 4
        )
    else:
        store = st.session_state.setdefault(_VALUES_STORE_KEY, {})
        # Capture values from the previously visible card before Streamlit
        # removes widget keys belonging to hidden Jobs.
        for job_id, param_key, param_data in _iter_parameters(workflow_data):
            key = _value_key(job_id, param_key)
            fallback = _starting_value(workflow_data, overrides, job_id, param_key, param_data)
            store.setdefault(job_id, {}).setdefault(param_key, fallback)
            if key in st.session_state:
                store[job_id][param_key] = st.session_state[key]

    _apply_pending_action(workflow_data, st.session_state[_VALUES_STORE_KEY])


def _apply_pending_action(
    workflow_data: Dict[str, Any],
    store: Dict[str, Dict[str, Any]],
) -> None:
    """Apply presets before the associated Streamlit widgets are created."""
    action = st.session_state.pop(_PENDING_ACTION_KEY, None)
    if not action:
        return

    kind = action.get("kind")
    if kind == "reset":
        for job_id, param_key, param_data in _iter_parameters(workflow_data):
            store.setdefault(job_id, {})[param_key] = param_data.get("value")
            st.session_state.pop(_value_key(job_id, param_key), None)
        st.session_state[_QUICK_DIAMETER_KEY] = store.get("J4", {}).get("diameter")
        st.session_state[_QUICK_PATH_KEY] = store.get("J1", {}).get("blob_paths") or ""
        st.session_state[_QUICK_GPU_KEY] = store.get("J2", {}).get("compute_num_gpus") or 4
        return

    return


def _quick_config_errors(diameter_A: Any, blob_paths: Any, gpu_count: Any) -> list[str]:
    """Validate the three experiment-specific inputs without touching disk."""
    errors: list[str] = []
    if not isinstance(diameter_A, (int, float)) or isinstance(diameter_A, bool) or diameter_A <= 0:
        errors.append("蛋白直径必须是大于 0 的数值。")
    elif diameter_A > 10000:
        errors.append("蛋白直径超出合理范围，请检查单位是否为 Å。")

    if not isinstance(blob_paths, str) or not blob_paths.strip():
        errors.append("数据路径不能为空。")
    elif len(blob_paths.strip()) > MAX_PATH_LENGTH:
        errors.append("数据路径过长，请缩短到 2048 个字符以内。")
    elif any(char in blob_paths for char in ("\x00", "\r", "\n")):
        errors.append("数据路径不能包含换行或空字符。")

    if (
        not isinstance(gpu_count, int)
        or isinstance(gpu_count, bool)
        or not 1 <= gpu_count <= MAX_GPU_COUNT
    ):
        errors.append(f"GPU 数量必须是 1 到 {MAX_GPU_COUNT} 之间的整数。")
    return errors


def _apply_quick_config(
    workflow_data: Dict[str, Any],
    store: Dict[str, Dict[str, Any]],
    *,
    diameter_A: float,
    blob_paths: str,
    gpu_count: int,
) -> Dict[str, int | float]:
    """Inject the quick form into every corresponding real template field."""
    clean_path = blob_paths.strip()
    for job_id, job in workflow_data.get("jobs", {}).items():
        parameters = job.get("parameters", {})
        updates: Dict[str, Any] = {}
        if "blob_paths" in parameters:
            updates["blob_paths"] = clean_path
        if "diameter" in parameters:
            updates["diameter"] = diameter_A
        if "diameter_max" in parameters:
            updates["diameter_max"] = diameter_A
        if "compute_num_gpus" in parameters:
            updates["compute_num_gpus"] = gpu_count
        if not updates:
            continue
        store.setdefault(job_id, {}).update(updates)
        for param_key in updates:
            # Hidden Streamlit widget keys are lifecycle-managed and may be
            # reclaimed on the next rerun. Keep the durable value only in the
            # editor store; the widget key is created when its Job is visible.
            st.session_state.pop(_value_key(job_id, param_key), None)

    return _sync_derived_parameters(workflow_data, store)


def _calculate_derived_parameters(
    diameter_A: Any,
    pixel_size_A: Any = None,
) -> Dict[str, int | float]:
    """Calculate linked extraction and mask values from the protein diameter."""
    if not isinstance(diameter_A, (int, float)) or diameter_A <= 0:
        return {}
    if not isinstance(pixel_size_A, (int, float)) or pixel_size_A <= 0:
        pixel_size_A = DEFAULT_PIXEL_SIZE_A

    mask_diameter = round(diameter_A / MASK_FILL_RATIO, 1)
    raw_box_size = diameter_A / MASK_FILL_RATIO / pixel_size_A * BOX_SIZE_SCALE
    box_size = int(math.ceil(raw_box_size / BOX_SIZE_ALIGNMENT) * BOX_SIZE_ALIGNMENT)
    return {
        "box_size_pix": box_size,
        "class2D_window_inner_A": mask_diameter,
        "pixel_size_A": float(pixel_size_A),
    }


def _sync_derived_parameters(
    workflow_data: Dict[str, Any],
    store: Dict[str, Dict[str, Any]],
) -> Dict[str, int | float]:
    """Write calculated values into every matching CryoSPARC Job."""
    diameter = store.get("J4", {}).get("diameter")
    pixel_size = store.get("J1", {}).get("psize_A")
    derived = _calculate_derived_parameters(diameter, pixel_size)
    if not derived:
        return {}

    jobs = workflow_data.get("jobs", {})
    for job_id, job in jobs.items():
        parameters = job.get("parameters", {})
        for param_key in DERIVED_PARAM_KEYS:
            if param_key not in parameters:
                continue
            value = derived[param_key]
            store.setdefault(job_id, {})[param_key] = value
            st.session_state.pop(_value_key(job_id, param_key), None)

    # A single diameter entered during onboarding represents an exact picker
    # size. Keep an invalid template maximum from falling below that value.
    picker_max = store.setdefault("J4", {}).get("diameter_max")
    if not isinstance(picker_max, (int, float)) or picker_max < diameter:
        store["J4"]["diameter_max"] = diameter
        st.session_state.pop(_value_key("J4", "diameter_max"), None)
    return derived


def _read_values(workflow_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    store = st.session_state.setdefault(_VALUES_STORE_KEY, {})
    values: Dict[str, Dict[str, Any]] = copy.deepcopy(store)
    for job_id, param_key, param_data in _iter_parameters(workflow_data):
        key = _value_key(job_id, param_key)
        values.setdefault(job_id, {})[param_key] = st.session_state.get(
            key, values.get(job_id, {}).get(param_key, param_data.get("value"))
        )
    st.session_state[_VALUES_STORE_KEY] = copy.deepcopy(values)
    return values


def _render_parameter_input(
    job_id: str,
    param_key: str,
    param_data: Dict[str, Any],
    *,
    required: bool = False,
    disabled: bool = False,
) -> None:
    store = st.session_state.setdefault(_VALUES_STORE_KEY, {})
    value = store.setdefault(job_id, {}).get(param_key, param_data.get("value"))
    label = PARAM_LABELS.get(param_key, param_key.replace("_", " "))
    unit = PARAM_UNITS.get(param_key)
    if unit:
        label = f"{label} ({unit})"
    if required:
        label = f"{label} *"
    key = _value_key(job_id, param_key)
    if key not in st.session_state:
        st.session_state[key] = value

    template_value = param_data.get("value")
    placeholder = REQUIRED_PLACEHOLDERS.get(param_key) if required else None
    help_text = "必填：请按本次实验实际情况确认。" if required else None

    if isinstance(template_value, bool):
        st.checkbox(label, key=key, disabled=disabled, help=help_text)
    elif isinstance(template_value, int) and not isinstance(template_value, bool):
        st.number_input(
            label, step=1, key=key, placeholder=placeholder,
            disabled=disabled, help=help_text,
        )
    elif isinstance(template_value, float):
        st.number_input(
            label, step=0.1, format="%.3f", key=key,
            placeholder=placeholder, disabled=disabled, help=help_text,
        )
    else:
        st.text_input(
            label, key=key, placeholder=placeholder,
            disabled=disabled, help=help_text,
        )

    store[job_id][param_key] = st.session_state[key]


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


def _workflow_lanes(
    jobs: Dict[str, Dict[str, Any]], levels: Dict[str, int]
) -> tuple[int, Dict[str, int]]:
    """Place each level on stable lanes, keeping single Jobs centred."""
    by_level: Dict[int, list[str]] = {}
    for job_id in jobs:
        by_level.setdefault(levels.get(job_id, 0), []).append(job_id)
    lane_count = max(3, max((len(row) for row in by_level.values()), default=1))
    lanes: Dict[str, int] = {}
    for row in by_level.values():
        if len(row) == 1:
            positions = [lane_count // 2]
        elif len(row) == 2:
            positions = [0, lane_count - 1]
        else:
            positions = [
                round(index * (lane_count - 1) / (len(row) - 1))
                for index in range(len(row))
            ]
        lanes.update(zip(row, positions))
    return lane_count, lanes


def _workflow_connector_markup(
    jobs: Dict[str, Dict[str, Any]],
    levels: Dict[str, int],
    lanes: Dict[str, int],
    lane_count: int,
    level: int,
) -> str:
    """Build the compact SVG segment between two adjacent workflow rows."""
    paths: list[str] = []
    carry_labels: list[str] = []
    targets: set[float] = set()
    for target_id, job in jobs.items():
        if levels.get(target_id) != level + 1:
            continue
        target_x = (lanes[target_id] + 0.5) * 100 / lane_count
        for source_id in _job_sources(job, jobs):
            source_level = levels.get(source_id)
            if source_level is None or source_level > level:
                continue
            if source_level == level:
                source_x = (lanes[source_id] + 0.5) * 100 / lane_count
                paths.append(
                    f'<path d="M {source_x:.3f} 1 C {source_x:.3f} 10, '
                    f'{target_x:.3f} 15, {target_x:.3f} 25" />'
                )
            else:
                label_y = 9 + len(carry_labels) * 6
                paths.append(
                    f'<path class="cswf-edge--carry" d="M 8 {label_y:.1f} '
                    f'C 24 {label_y:.1f}, {target_x:.3f} 15, {target_x:.3f} 25" />'
                )
                carry_labels.append(
                    f'<span class="cswf-carry-label" style="top:{max(label_y - 3, 0):.1f}px">'
                    f'{html.escape(source_id)}</span>'
                )
            targets.add(target_x)
    if not paths:
        return '<div class="cswf-edge-row cswf-edge-row--empty"></div>'
    dots = "".join(
        f'<circle cx="{target_x:.3f}" cy="25" r="2.2" />'
        for target_x in sorted(targets)
    )
    return (
        '<div class="cswf-edge-row" aria-hidden="true">'
        '<svg viewBox="0 0 100 27" preserveAspectRatio="none">'
        + "".join(paths)
        + dots
        + "</svg>"
        + "".join(carry_labels)
        + "</div>"
    )


def _render_interactive_workflow(workflow_data: Dict[str, Any], active_job: str) -> None:
    jobs = workflow_data.get("jobs", {})
    levels = _job_levels(jobs)
    max_level = max(levels.values(), default=0)
    lane_count, lanes = _workflow_lanes(jobs, levels)
    connection_count = sum(len(_job_sources(job, jobs)) for job in jobs.values())

    st.markdown(
        f"""
        <div class="cswf-canvas-title">
          <div>
            <span class="cswf-canvas-kicker">PROCESS MAP</span>
            <h4>Workflow</h4>
          </div>
          <div class="cswf-canvas-summary">{len(jobs)} Jobs&nbsp;&nbsp;·&nbsp;&nbsp;{connection_count} Connections</div>
        </div>
        <div class="cswf-canvas-legend">
          <span><i class="cswf-legend-dot cswf-legend-dot--active"></i>当前编辑</span>
          <span><i class="cswf-legend-dot"></i>可编辑节点</span>
          <span><i class="cswf-legend-line"></i>数据流</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True, key="cswf_workflow_canvas"):
        with st.container(key="cswf_graph_inner"):
            for level in range(max_level + 1):
                current = [job_id for job_id in jobs if levels.get(job_id) == level]
                if not current:
                    continue
                column_widths = [1] * lane_count
                if len(current) == 1:
                    column_widths[lanes[current[0]]] = 2
                columns = st.columns(column_widths, gap="medium")
                for job_id in current:
                    col = columns[lanes[job_id]]
                    job = jobs[job_id]
                    with col:
                        with st.container(key=f"cswf_shell_{job_id}"):
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
                            sources = _job_sources(job, jobs)
                            phase = JOB_PHASE_LABELS.get(job.get("jobType", ""), "JOB")
                            phase_class = phase.lower() if phase in JOB_PHASE_LABELS.values() else "job"
                            parameter_count = len(job.get("parameters", {}))
                            parameter_label = "param" if parameter_count == 1 else "params"
                            source_text = " + ".join(sources) if sources else "source"
                            st.markdown(
                                '<div class="cswf-node-meta">'
                                '<span class="cswf-node-meta-main">'
                                f'<b class="cswf-node-phase cswf-node-phase--{phase_class}">'
                                f'{html.escape(phase)}</b>'
                                f'<span>{parameter_count} {parameter_label}</span></span>'
                                f'<span class="cswf-node-source">← {html.escape(source_text)}</span>'
                                "</div>",
                                unsafe_allow_html=True,
                            )
                if level < max_level:
                    st.markdown(
                        _workflow_connector_markup(jobs, levels, lanes, lane_count, level),
                        unsafe_allow_html=True,
                    )


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


def _workflow_validation_errors(
    values: Dict[str, Dict[str, Any]],
    workflow_data: Optional[Dict[str, Any]] = None,
) -> list[str]:
    """Return user-facing errors for invalid cross-field combinations."""
    picker = values.get("J4", {})
    diameter_min = picker.get("diameter")
    diameter_max = picker.get("diameter_max")
    errors: list[str] = []

    if not isinstance(diameter_min, (int, float)) or isinstance(diameter_min, bool):
        errors.append("J4 颗粒直径下限必须是数值。")
    elif diameter_min <= 0:
        errors.append("J4 颗粒直径下限必须大于 0 Å。")
    if (
        not isinstance(diameter_max, (int, float))
        or isinstance(diameter_max, bool)
        or diameter_max <= 0
    ):
        errors.append("J4 颗粒直径上限必须大于 0 Å。")
    if (
        isinstance(diameter_min, (int, float))
        and isinstance(diameter_max, (int, float))
        and diameter_max < diameter_min
    ):
        errors.append("J4 颗粒直径上限不能小于下限。")

    for job_id, job in (workflow_data or {}).get("jobs", {}).items():
        for param_key, param_data in job.get("parameters", {}).items():
            if not _is_required_parameter(job, param_key):
                continue
            value = values.get(job_id, {}).get(param_key)
            missing = value is None or (isinstance(value, str) and not value.strip())
            label = PARAM_LABELS.get(param_key, param_key.replace("_", " "))
            if missing:
                errors.append(f"{job_id} {label}为必填项。")
            elif (
                param_key != "diameter"
                and isinstance(value, (int, float))
                and value <= 0
            ):
                errors.append(f"{job_id} {label}必须大于 0。")

        for param_key in DERIVED_PARAM_KEYS:
            if param_key not in job.get("parameters", {}):
                continue
            value = values.get(job_id, {}).get(param_key)
            label = PARAM_LABELS[param_key]
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"{job_id} {label}必须是大于 0 的数值。")
            elif param_key == "box_size_pix" and int(value) % 2 != 0:
                errors.append(f"{job_id} {label}必须是偶数像素。")

    if workflow_data is None:
        return errors

    import_values = values.get("J1", {})
    blob_paths = import_values.get("blob_paths")
    path_errors = _quick_config_errors(
        diameter_min,
        blob_paths,
        1,
    )
    for message in path_errors:
        if message.startswith("数据路径") and message not in errors:
            errors.append(message)

    pixel_size = import_values.get("psize_A")
    if not isinstance(pixel_size, (int, float)) or isinstance(pixel_size, bool) or pixel_size <= 0:
        errors.append("J1 像素大小必须是大于 0 的数值。")
    elif isinstance(diameter_min, (int, float)) and diameter_min > 0:
        minimum_physical_box = diameter_min * MIN_BOX_PADDING_RATIO
        for job_id, job_values in values.items():
            box_size = job_values.get("box_size_pix")
            if isinstance(box_size, (int, float)) and box_size * pixel_size < minimum_physical_box:
                errors.append(
                    f"{job_id} Extraction box size 过小：物理边长至少应为蛋白直径的 "
                    f"{MIN_BOX_PADDING_RATIO:.1f} 倍。"
                )

    first_box = values.get("J5", {}).get("box_size_pix")
    second_box = values.get("J8", {}).get("box_size_pix")
    if first_box is not None and second_box is not None and first_box != second_box:
        errors.append("J5 与 J8 的 Extraction box size 必须保持一致。")

    for job_id, job_values in values.items():
        gpu_count = job_values.get("compute_num_gpus")
        if gpu_count is None:
            continue
        if (
            not isinstance(gpu_count, int)
            or isinstance(gpu_count, bool)
            or not 0 <= gpu_count <= MAX_GPU_COUNT
        ):
            errors.append(f"{job_id} GPU 数量必须是 0 到 {MAX_GPU_COUNT} 之间的整数。")
    return errors


def _workflow_validation_warnings(values: Dict[str, Dict[str, Any]]) -> list[str]:
    """Return non-blocking guidance for unusual but importable values."""
    warnings: list[str] = []
    blob_paths = values.get("J1", {}).get("blob_paths")
    if isinstance(blob_paths, str) and blob_paths.strip() and not any(
        marker in blob_paths for marker in ("*", "?", "[")
    ):
        warnings.append("数据路径未包含通配符；如果只需导入单个文件可以忽略此提示。")
    for job_id, job_values in values.items():
        gpu_count = job_values.get("compute_num_gpus")
        if isinstance(gpu_count, int) and gpu_count > 8:
            warnings.append(f"{job_id} 使用 {gpu_count} 张 GPU，请确认集群资源允许。")
        box_size = job_values.get("box_size_pix")
        if isinstance(box_size, int) and box_size % BOX_SIZE_ALIGNMENT != 0:
            warnings.append(
                f"{job_id} Extraction box size 不是 {BOX_SIZE_ALIGNMENT} 的倍数；"
                "仍可导出，但 FFT 性能可能较低。"
            )
    return warnings


def render_workflow_config(
    workflow_path: Path,
    initial_params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Render editable cards and return an export-ready configuration on confirm.

    ``None`` means the user is still editing.  A returned value carries both
    conventional StructPilot parameter names and the full CryoSPARC template
    plus per-job overrides for exact JSON export.
    """
    try:
        workflow_data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except OSError:
        st.error("无法读取 workflow 模板，请联系管理员检查部署文件。")
        return None
    except json.JSONDecodeError:
        st.error("workflow 模板不是有效的 JSON，已停止生成以避免导出损坏文件。")
        return None

    template_errors = _template_validation_errors(workflow_data)
    if template_errors:
        st.error("workflow 模板结构校验失败，已停止生成。")
        for message in template_errors[:5]:
            st.caption(message)
        return None

    jobs = workflow_data["jobs"]
    _initialise_editor(workflow_path, workflow_data, initial_params)

    st.markdown(
        """
        <style>
        .cswf-head { margin: 0.2rem 0 0.45rem; }
        .cswf-head h2 { margin: 0; font-size: 1.45rem !important; }
        .cswf-phase { color: #475569; font-size: 0.82rem; font-weight: 700; margin-bottom: 0.2rem; }
        .cswf-canvas-title {
          display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
          flex-wrap: wrap; margin: 0.05rem 0 0.55rem;
        }
        .cswf-canvas-title h4 { margin: 0.05rem 0 0 !important; font-size: 1.05rem !important; }
        .cswf-canvas-kicker {
          color: #2879b9; font-size: 0.63rem; font-weight: 800; letter-spacing: 0.12em;
        }
        .cswf-canvas-summary { color: #64748b; font-size: 0.7rem; white-space: nowrap; }
        .cswf-canvas-legend {
          display: flex; align-items: center; gap: 1rem; margin: -0.1rem 0 0.55rem;
          color: #64748b; font-size: 0.7rem;
        }
        .cswf-canvas-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
        .cswf-legend-dot { width: 0.46rem; height: 0.46rem; border-radius: 50%; background: #94a3b8; }
        .cswf-legend-dot--active { background: #1683d8; box-shadow: 0 0 0 3px #e2f1fc; }
        .cswf-legend-line { width: 1.15rem; height: 1px; background: #a8bacb; }
        div.st-key-cswf_workflow_canvas {
          border-color: #d3dee8 !important; background: #f8fafc;
          padding: 1rem 0.8rem 0.85rem !important;
          box-shadow: 0 2px 7px rgba(15, 23, 42, 0.035);
        }
        div.st-key-cswf_graph_inner {
          width: min(100%, 780px); margin: 0 auto;
        }
        div[class*="st-key-cswf_shell_"] {
          width: min(100%, 240px); margin: 0 auto !important;
        }
        div[class*="st-key-cswf_shell_"] > div[data-testid="stVerticalBlock"] {
          gap: 0 !important;
        }
        div[class*="st-key-cswf_node_"] { width: 100%; margin: 0 !important; }
        div[class*="st-key-cswf_shell_"] div[data-testid="stButton"] > button {
          display: flex !important; width: 100% !important;
          min-width: 100% !important; max-width: 100% !important;
          box-sizing: border-box !important;
        }
        div[class*="st-key-cswf_node_"] button {
          width: 100% !important; min-height: 3.35rem; justify-content: flex-start; text-align: left;
          padding: 0.55rem 0.72rem; border-radius: 6px 6px 4px 4px;
          border: 1px solid #cbd7e2; background: #ffffff; color: #203246;
          box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
          transition: border-color 120ms ease, box-shadow 120ms ease, background 120ms ease;
        }
        div[class*="st-key-cswf_node_"] button::before {
          content: ""; flex: 0 0 auto; width: 0.46rem; height: 0.46rem;
          border-radius: 50%; background: #8ea1b3; margin-right: 0.25rem;
        }
        div[class*="st-key-cswf_node_"] button:hover {
          border-color: #70a9d5; background: #fbfdff;
          box-shadow: 0 3px 9px rgba(43, 104, 153, 0.1);
        }
        div[class*="st-key-cswf_node_"] button[data-testid="stBaseButton-primary"] {
          border-color: #1683d8; background: #eaf4fb; color: #0b5f9f;
          box-shadow: inset 3px 0 0 #1683d8, 0 2px 8px rgba(22, 131, 216, 0.13);
        }
        div[class*="st-key-cswf_node_"] button[data-testid="stBaseButton-primary"]::before {
          background: #1683d8; box-shadow: 0 0 0 3px rgba(22, 131, 216, 0.13);
        }
        div[class*="st-key-cswf_node_"] button p {
          font-size: 0.78rem !important; font-weight: 680; line-height: 1.22;
          white-space: normal; letter-spacing: 0;
        }
        .cswf-node-meta {
          display: flex; align-items: center; justify-content: space-between; gap: 0.35rem;
          width: 100%; min-height: 1.35rem;
          margin: -1px 0 0; padding: 0.34rem 0.48rem 0.22rem;
          border: 1px solid #dbe3ea; border-top: 0; border-radius: 0 0 5px 5px;
          background: rgba(255,255,255,0.72); color: #6b7d90;
          font-size: 0.61rem; line-height: 1.1; white-space: nowrap;
        }
        .cswf-node-meta-main { display: inline-flex; align-items: center; gap: 0.34rem; }
        .cswf-node-phase { font-size: 0.58rem; font-weight: 800; letter-spacing: 0.055em; }
        .cswf-node-phase--import { color: #0f766e; }
        .cswf-node-phase--preprocess { color: #a16207; }
        .cswf-node-phase--curate { color: #536779; }
        .cswf-node-phase--pick { color: #15803d; }
        .cswf-node-phase--extract { color: #2563a7; }
        .cswf-node-phase--classify { color: #6d4aae; }
        .cswf-node-phase--select { color: #475569; }
        .cswf-node-phase--job { color: #64748b; }
        .cswf-node-source { color: #526b82; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .cswf-edge-row { position: relative; height: 1.35rem; margin: -0.05rem 0; overflow: visible; }
        .cswf-edge-row svg { display: block; width: 100%; height: 100%; overflow: visible; }
        .cswf-edge-row path {
          fill: none; stroke: #91a8ba; stroke-width: 1.05; vector-effect: non-scaling-stroke;
        }
        .cswf-edge-row path.cswf-edge--carry {
          stroke: #5f86a5; stroke-width: 1; stroke-dasharray: 4 3;
        }
        .cswf-edge-row circle { fill: #587b96; }
        .cswf-carry-label {
          position: absolute; left: 0.05rem; z-index: 1; display: inline-flex;
          align-items: center; justify-content: center; min-width: 1.45rem; height: 1rem;
          padding: 0 0.26rem; border: 1px solid #b8cad8; border-radius: 3px;
          background: #f8fafc; color: #41647e; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 0.55rem; font-weight: 750; line-height: 1;
        }
        .cswf-edge-row--empty { height: 0.8rem; }
        div[class*="st-key-cswf_card_selector_"] button {
          width: 100%; min-height: 2.25rem; border-radius: 5px; padding: 0.25rem 0.45rem;
          border-color: #d5dee7; color: #44576a; background: #ffffff;
        }
        div[class*="st-key-cswf_card_selector_"] button p {
          font-size: 0.72rem !important; font-weight: 650;
        }
        div[class*="st-key-cswf_card_selector_"] button[data-testid="stBaseButton-primary"] {
          border-color: #1683d8; color: #0b5f9f; background: #eaf4fb;
          box-shadow: inset 3px 0 0 #1683d8;
        }
        @media (max-width: 900px) {
          .cswf-canvas-summary { display: none; }
          .cswf-canvas-legend { gap: 0.6rem; flex-wrap: wrap; }
          div.st-key-cswf_workflow_canvas { padding: 0.7rem 0.6rem 0.55rem !important; }
          div.st-key-cswf_graph_inner { width: 100%; }
          div[class*="st-key-cswf_node_"] button { min-height: 2.9rem; padding: 0.38rem 0.42rem; }
          div[class*="st-key-cswf_node_"] button p { font-size: 0.68rem !important; }
          .cswf-node-meta { padding-inline: 0.28rem; font-size: 0.52rem; }
          .cswf-node-phase { font-size: 0.5rem; }
        }
        </style>
        <div class='cswf-head'><h2>🎯 cryoSPARC Workflow 参数填写</h2></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "基于课题组真实导出的 cryoSPARC v4.4.1 2D 分类模板。"
        "默认值可直接采用，也可展开逐项修改。"
    )

    if not st.session_state.get(_QUICK_READY_KEY, False):
        st.session_state.setdefault(
            _QUICK_DIAMETER_INPUT_KEY, st.session_state.get(_QUICK_DIAMETER_KEY)
        )
        st.session_state.setdefault(
            _QUICK_PATH_INPUT_KEY, st.session_state.get(_QUICK_PATH_KEY, "")
        )
        st.session_state.setdefault(
            _QUICK_GPU_INPUT_KEY, st.session_state.get(_QUICK_GPU_KEY, 4)
        )
        st.markdown("<div class='cswf-phase'>第一步 · 3 项基础信息</div>", unsafe_allow_html=True)
        quick_cols = st.columns([1.0, 1.7, 0.8], gap="medium")
        with quick_cols[0]:
            st.number_input(
                "蛋白直径 (Å) *",
                min_value=1.0,
                max_value=10000.0,
                step=1.0,
                placeholder="根据蛋白大小填写，如 120",
                key=_QUICK_DIAMETER_INPUT_KEY,
            )
        with quick_cols[1]:
            st.text_input(
                "数据路径 *",
                placeholder="根据课题组数据路径填写，如 /project/data/*.mrc",
                max_chars=MAX_PATH_LENGTH,
                key=_QUICK_PATH_INPUT_KEY,
            )
        with quick_cols[2]:
            st.number_input(
                "GPU 数量 *",
                min_value=1,
                max_value=MAX_GPU_COUNT,
                step=1,
                help="会预填到模板内所有包含 compute_num_gpus 的 Job，之后仍可逐节点修改。",
                key=_QUICK_GPU_INPUT_KEY,
            )

        if st.button(
            "一键生成 Workflow",
            key="cswf_quick_generate",
            type="primary",
            use_container_width=True,
        ):
            quick_errors = _quick_config_errors(
                st.session_state.get(_QUICK_DIAMETER_INPUT_KEY),
                st.session_state.get(_QUICK_PATH_INPUT_KEY),
                st.session_state.get(_QUICK_GPU_INPUT_KEY),
            )
            if quick_errors:
                for message in quick_errors:
                    st.error(message)
            else:
                st.session_state[_QUICK_DIAMETER_KEY] = st.session_state[_QUICK_DIAMETER_INPUT_KEY]
                st.session_state[_QUICK_PATH_KEY] = st.session_state[_QUICK_PATH_INPUT_KEY].strip()
                st.session_state[_QUICK_GPU_KEY] = st.session_state[_QUICK_GPU_INPUT_KEY]
                st.session_state[_AUTO_DERIVE_KEY] = True
                _apply_quick_config(
                    workflow_data,
                    st.session_state[_VALUES_STORE_KEY],
                    diameter_A=st.session_state[_QUICK_DIAMETER_KEY],
                    blob_paths=st.session_state[_QUICK_PATH_KEY],
                    gpu_count=st.session_state[_QUICK_GPU_KEY],
                )
                st.session_state[_ACTIVE_JOB_KEY] = "J1" if "J1" in jobs else next(iter(jobs))
                st.session_state[_QUICK_READY_KEY] = True
                st.rerun()
        return None

    auto_derive = bool(st.session_state.setdefault(_AUTO_DERIVE_KEY, True))
    derived_values: Dict[str, int | float] = {}
    if auto_derive:
        derived_values = _sync_derived_parameters(
            workflow_data, st.session_state[_VALUES_STORE_KEY]
        )
    active_job = st.session_state.get(_ACTIVE_JOB_KEY)
    if active_job not in jobs:
        active_job = next(iter(jobs))
        st.session_state[_ACTIVE_JOB_KEY] = active_job

    summary_cols = st.columns([1, 1.7, 0.8, 0.9], gap="small")
    summary_cols[0].metric("蛋白直径", f"{st.session_state.get(_QUICK_DIAMETER_KEY):g} Å")
    summary_cols[1].text_input(
        "当前数据路径",
        value=st.session_state.get(_QUICK_PATH_KEY, ""),
        disabled=True,
        label_visibility="collapsed",
    )
    summary_cols[2].metric("GPU", st.session_state.get(_QUICK_GPU_KEY, 4))
    with summary_cols[3]:
        if st.button("修改基础信息", key="cswf_back_to_quick", use_container_width=True):
            st.session_state[_QUICK_DIAMETER_INPUT_KEY] = st.session_state.get(_QUICK_DIAMETER_KEY)
            st.session_state[_QUICK_PATH_INPUT_KEY] = st.session_state.get(_QUICK_PATH_KEY, "")
            st.session_state[_QUICK_GPU_INPUT_KEY] = st.session_state.get(_QUICK_GPU_KEY, 4)
            st.session_state[_QUICK_READY_KEY] = False
            st.rerun()

    left_col, right_col = st.columns([0.9, 1.7], gap="large")
    with left_col:
        st.markdown("#### 参数设置")
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

        job = jobs[active_job]
        required_parameters, recommended_parameters = _partition_parameters(job)
        _read_values(workflow_data)

        manual_tab, recommended_tab = st.tabs(["必填输入", "推荐与高级"])
        with manual_tab:
            st.markdown(f"##### {active_job} · {_job_label(active_job, job)}")
            for param_key, param_data in required_parameters:
                _render_parameter_input(
                    active_job, param_key, param_data, required=True
                )

        with recommended_tab:
            with st.expander("查看和编辑课题组推荐参数", expanded=False):
                has_derived_parameter = any(
                    param_key in DERIVED_PARAM_KEYS
                    for param_key, _ in recommended_parameters
                )
                if has_derived_parameter:
                    st.checkbox(
                        "自动换算 box size 与 circular mask",
                        key=_AUTO_DERIVE_KEY,
                        help=(
                            "开启时按蛋白直径、实际像素尺寸、2.0 倍边界系数和 16 像素对齐自动计算；"
                            "关闭后即可手动覆盖。"
                        ),
                    )
                    if auto_derive and derived_values:
                        st.caption(
                            "自动：box = ceil(直径 / 0.9 / "
                            f"{derived_values['pixel_size_A']:.3f} × {BOX_SIZE_SCALE} / "
                            f"{BOX_SIZE_ALIGNMENT}) × {BOX_SIZE_ALIGNMENT}；mask = 直径 / 0.9。"
                        )

                for param_key, param_data in recommended_parameters:
                    _render_parameter_input(
                        active_job,
                        param_key,
                        param_data,
                        disabled=auto_derive and param_key in DERIVED_PARAM_KEYS,
                    )

                st.divider()
                st.caption("参数来源：课题组真实跑通的 cryoSPARC v4.4.1 Workflow JSON。")
                if st.button("恢复课题组模板值", key="cswf_reset", use_container_width=True):
                    st.session_state[_PENDING_ACTION_KEY] = {"kind": "reset"}
                    st.rerun()

        st.divider()
        live_values = _read_values(workflow_data)
        live_errors = _workflow_validation_errors(live_values, workflow_data)
        live_warnings = _workflow_validation_warnings(live_values)
        if live_errors:
            st.error(f"发现 {len(live_errors)} 项需修正的问题")
            with st.expander("查看校验详情", expanded=False):
                for message in live_errors:
                    st.write(f"- {message}")
        elif live_warnings:
            st.warning("参数可导出，但有建议检查项")
            with st.expander("查看提示", expanded=False):
                for message in live_warnings:
                    st.write(f"- {message}")
        else:
            st.success("参数与跨节点连接校验通过")
        confirmed = st.button(
            "确认并生成可导入 JSON",
            key="cswf_confirm",
            type="primary",
            use_container_width=True,
            disabled=bool(live_errors),
        )

    with right_col:
        _render_interactive_workflow(workflow_data, active_job)

    if not confirmed:
        return None

    values = _read_values(workflow_data)
    validation_errors = _workflow_validation_errors(values, workflow_data)
    if validation_errors:
        st.error("参数在生成前发生变化，请修正后重试。")
        return None

    result = _canonical_parameters(values)
    result["_workflow_template"] = copy.deepcopy(workflow_data)
    result["_workflow_values"] = values
    return result


def save_workflow_config(user_params: Dict[str, Any], output_path: Path) -> bool:
    """Save editor state for recovery; final imports use the workflow generator."""
    try:
        from utils.atomic_io import atomic_write_json
        atomic_write_json(output_path, user_params)
        return True
    except OSError as exc:
        st.error(f"保存失败: {exc}")
        return False
