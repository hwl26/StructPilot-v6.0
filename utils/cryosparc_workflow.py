"""StructPilot v6.0 — CryoSPARC Workflow JSON 生成器（官方格式）。

根据 CryoSPARC v4.4+ 官方 Workflow 格式生成可导入的 JSON。
参考官方示例结构并验证字段完整性。
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
_CHECKPOINTS_PATH = BASE_DIR / "knowledge_base" / "flows" / "pipeline_checkpoints.json"

# CryoSPARC job_type 映射（扩展版，对照真实样本）
_JOB_TYPE_MAP: dict[str, str] = {
    "cp_01": "import_movies",
    "cp_01b": "import_micrographs",  # RELION接力路线
    "cp_02": "patch_motion_correction_multi",
    "cp_03": "patch_ctf_estimation_multi",
    "cp_03b": "curate_exposures_v2",  # 人工筛选
    "cp_03c": "denoise_train",  # 降噪训练
    "cp_04": "blob_picker_gpu",
    "cp_04b": "template_picker_gpu",  # 模板匹配
    "cp_04c": "inspect_picks_v2",  # 检查挑选结果
    "cp_05": "extract_micrographs_multi",
    "cp_06": "class_2D_new",
    "cp_06b": "select_2D",  # 2D分类筛选
    "cp_07": "homo_abinit",
    "cp_08": "hetero_refine",
    "cp_09": "homo_refine_new",
    "cp_09b": "nonuniform_refine_new",  # 非均匀精修
    "cp_10": "ctf_refinement",
    "cp_11": "sharpen",
    "cp_12": "local_resolution",
}

# 数据流连接（扩展版，支持分支路线）
_CONNECTIONS: dict[str, list[tuple[str, str, str]]] = {
    "cp_02": [("cp_01", "imported_movies", "movies")],
    "cp_03": [("cp_02", "micrographs", "exposures")],
    "cp_03b": [("cp_03", "exposures", "exposures")],  # curate_exposures
    "cp_03c": [("cp_03b", "exposures_accepted", "exposures")],  # denoise_train（可选）
    "cp_04": [("cp_03b", "exposures_accepted", "micrographs")],  # blob_picker 接筛选后的
    "cp_04c": [("cp_04", "particles", "particles"), ("cp_04", "micrographs", "micrographs")],  # inspect_picks
    "cp_05": [
        ("cp_04c", "micrographs", "micrographs"),  # 如果有 inspect_picks
        ("cp_04c", "particles", "particles"),
    ],
    "cp_06": [("cp_05", "particles", "particles")],
    "cp_06b": [("cp_06", "particles", "particles"), ("cp_06", "class_averages", "templates")],  # select_2D
    "cp_07": [("cp_06b", "particles_selected", "particles")],  # abinit 接筛选后的颗粒
    "cp_08": [
        ("cp_06b", "particles_selected", "particles"),
        ("cp_07", "volume_class_0", "volume"),
    ],
    "cp_09": [
        ("cp_08", "particles_class_0", "particles"),
        ("cp_08", "volume_class_0", "volume"),
    ],
    "cp_09b": [  # nonuniform_refine
        ("cp_09", "particles", "particles"),
        ("cp_09", "volume", "volume"),
        ("cp_09", "mask", "mask"),
    ],
    "cp_10": [
        ("cp_09", "particles", "particles"),
        ("cp_09", "volume", "volume"),
    ],
    "cp_11": [
        ("cp_10", "particles", "particles"),
        ("cp_10", "volume", "volume"),
    ],
    "cp_12": [("cp_11", "map_sharp", "volume")],
}


def _param(value: Any, locked: bool = False, visible: bool = True, flagged: bool = False) -> dict:
    """生成可继续编辑的 CryoSPARC 参数对象格式。"""
    return {
        "value": value,
        # StructPilot exports are intended as editable starting points.  Never
        # carry a locked field into CryoSPARC, even for generated defaults.
        "locked": False,
        "visible": visible,
        "flagged": flagged,
        "notes": "",
    }


def _validated_parameter_value(expected: Any, candidate: Any, field_name: str) -> Any:
    """Reject session-state type confusion before serializing an export."""
    if isinstance(expected, bool):
        if not isinstance(candidate, bool):
            raise ValueError(f"{field_name} must be a boolean")
        return candidate
    if isinstance(expected, int):
        if not isinstance(candidate, int) or isinstance(candidate, bool):
            raise ValueError(f"{field_name} must be an integer")
        return candidate
    if isinstance(expected, float):
        if not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
            raise ValueError(f"{field_name} must be numeric")
        return float(candidate)
    if isinstance(expected, str):
        if not isinstance(candidate, str):
            raise ValueError(f"{field_name} must be text")
        if len(candidate) > 10000 or any(char in candidate for char in ("\x00", "\r", "\n")):
            raise ValueError(f"{field_name} contains unsupported text")
        return candidate
    if candidate is not None and not isinstance(candidate, (str, int, float, bool)):
        raise ValueError(f"{field_name} must be a JSON scalar")
    return candidate


def materialize_workflow_template(
    template: dict,
    values: dict,
    workflow_name: str,
) -> dict:
    """Apply editor values to a CryoSPARC template without changing topology.

    The workflow editor receives a real exported CryoSPARC workflow.  Keeping
    its jobs, groups and job types intact is essential: reconstructing it from
    a simplified list of steps loses the routing required by import.
    """
    workflow_json = copy.deepcopy(template)
    jobs = workflow_json.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise ValueError("CryoSPARC workflow template must contain a jobs object")

    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            raise ValueError(f"CryoSPARC workflow job {job_id} must be an object")
        if not isinstance(job.get("jobType"), str) or not job.get("jobType"):
            raise ValueError(f"CryoSPARC workflow job {job_id} must contain jobType")
        groups = job.get("groups")
        if not isinstance(groups, list):
            raise ValueError(f"CryoSPARC workflow job {job_id} must contain groups")
        for group in groups:
            if not isinstance(group, list) or len(group) != 2:
                raise ValueError(f"CryoSPARC workflow job {job_id} has an invalid group")
            source = group[0]
            if not isinstance(source, str) or "." not in source:
                raise ValueError(f"CryoSPARC workflow job {job_id} has an invalid source")
            if source.split(".", 1)[0] not in jobs:
                raise ValueError(f"CryoSPARC workflow job {job_id} references a missing source")
        parameters = job.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError(f"CryoSPARC workflow job {job_id} must contain parameters")
        job_values = values.get(job_id, {}) if isinstance(values, dict) else {}
        for key, parameter in parameters.items():
            if not isinstance(parameter, dict):
                raise ValueError(f"CryoSPARC parameter {job_id}.{key} must be an object")
            if "value" not in parameter:
                raise ValueError(f"CryoSPARC parameter {job_id}.{key} must contain value")
            if isinstance(job_values, dict) and key in job_values:
                parameter["value"] = _validated_parameter_value(
                    parameter.get("value"), job_values[key], f"{job_id}.{key}"
                )
            parameter["locked"] = False
            parameter["visible"] = bool(parameter.get("visible", True))
            parameter["flagged"] = bool(parameter.get("flagged", False))
            parameter["notes"] = str(parameter.get("notes", ""))

    workflow_json["_id"] = uuid.uuid4().hex[:24]
    workflow_json["createdAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    clean_name = str(workflow_name).strip()
    if not clean_name or len(clean_name) > 200 or any(
        char in clean_name for char in ("\x00", "\r", "\n")
    ):
        raise ValueError("CryoSPARC workflow name is invalid")
    workflow_json["title"] = clean_name
    workflow_json["description"] = "Generated by StructPilot from an editable CryoSPARC workflow template."
    workflow_json.setdefault("category", "")
    workflow_json["createdBy"] = ""
    workflow_json.setdefault("csVersion", "v4.4.1")
    workflow_json.setdefault("parents", {})
    workflow_json.setdefault("workflowVersion", "1.0.0")
    return workflow_json


def _load_checkpoints() -> dict[str, dict]:
    """加载 checkpoint 元数据。"""
    try:
        data = json.loads(_CHECKPOINTS_PATH.read_text(encoding="utf-8"))
        return {cp["checkpoint_id"]: cp for cp in data}
    except Exception:
        return {}


def generate_cryosparc_workflow(
    workflow: dict,
    params: dict,
    workflow_name: str = "StructPilot_Workflow",
    software: str = "cryosparc",
) -> dict | None:
    """生成 CryoSPARC v4.4+ 官方格式的 Workflow JSON。

    Parameters
    ----------
    workflow : dict
        StructPilot 推荐工作流，格式：{"steps": [...], "skip_steps": [...]}
    params : dict
        用户采集参数（pixel_size, voltage, Cs, particle_diameter, box_size等）
    workflow_name : str
        Workflow 显示名称
    software : str
        软件标识（非 cryosparc 时返回 None）

    Returns
    -------
    dict | None
        CryoSPARC Workflow JSON 对象，可直接序列化后导入 CryoSPARC GUI。
        格式兼容 CryoSPARC v4.4+
    """
    if software.lower() not in ("cryosparc", "cryosparc4", "cs"):
        return None

    template = params.get("_workflow_template")
    if isinstance(template, dict):
        return materialize_workflow_template(
            template,
            params.get("_workflow_values", {}),
            workflow_name,
        )

    steps = [s for s in workflow.get("steps", []) if s not in workflow.get("skip_steps", [])]
    if not steps:
        return None

    checkpoints = _load_checkpoints()
    jobs: dict[str, dict] = {}
    job_id_map: dict[str, str] = {}  # cp_id → J1/J2/...

    # 生成 Job 节点
    for idx, cp_id in enumerate(steps):
        job_type = _JOB_TYPE_MAP.get(cp_id)
        if not job_type:
            continue

        job_id = f"J{idx + 1}"
        job_id_map[cp_id] = job_id
        cp_meta = checkpoints.get(cp_id, {})

        # 构建 groups（数据流连接）
        groups: list[list[str]] = []
        if cp_id in _CONNECTIONS:
            for src_cp, src_slot, dst_slot in _CONNECTIONS[cp_id]:
                if src_cp in job_id_map:
                    groups.append([f"{job_id_map[src_cp]}.{src_slot}", dst_slot])

        # 构建 parameters（对照真实 cryoSPARC workflow 样本）
        job_params: dict[str, dict] = {}

        # cp_01: Import Movies
        if cp_id == "cp_01":
            job_params = {
                "blob_paths": _param(params.get("movies_path"), locked=False, visible=True, flagged=True),
                "gainref_path": _param(params.get("gainref_path"), locked=False, visible=True, flagged=True),
                "psize_A": _param(params.get("pixel_size", 0.41), locked=False, visible=True, flagged=True),
                "accel_kv": _param(params.get("voltage", 300), locked=True, visible=True, flagged=False),
                "cs_mm": _param(params.get("Cs", 2.7), locked=True, visible=True, flagged=False),
                "total_dose_e_per_A2": _param(params.get("total_dose", 60), locked=True, visible=True, flagged=False),
            }

        # cp_02: Motion Correction
        elif cp_id == "cp_02":
            job_params = {
                "bfactor": _param(150, locked=True, visible=True, flagged=False),
                "output_fcrop_factor": _param("1/2", locked=True, visible=True, flagged=False),  # 字符串格式！
                "compute_num_gpus": _param(params.get("motion_gpus", 4), locked=True, visible=True, flagged=False),
                "output_f16": _param(True, locked=True, visible=True, flagged=False),
            }

        # cp_03: CTF Estimation
        elif cp_id == "cp_03":
            job_params = {
                "compute_num_gpus": _param(params.get("ctf_gpus", 4), locked=True, visible=True, flagged=False),
            }

        # cp_04: Blob Picker
        elif cp_id == "cp_04":
            diameter = params.get("particle_diameter", 150)
            # 防止 diameter 为 None 导致的 TypeError
            if diameter is None:
                diameter = 150
            diameter_max = params.get("particle_diameter_max") or (diameter * 1.5)
            job_params = {
                "diameter": _param(diameter, locked=False, visible=True, flagged=True),
                "diameter_max": _param(diameter_max, locked=False, visible=True, flagged=True),
                "max_num_hits": _param(params.get("max_num_hits", 300), locked=False, visible=True, flagged=False),
                "min_distance": _param(0.6, locked=False, visible=True, flagged=False),
                "use_ellipse": _param(True, locked=False, visible=True, flagged=False),
                "use_circle": _param(False, locked=False, visible=True, flagged=False),
                "use_denoised": _param(params.get("use_denoised", True), locked=True, visible=True, flagged=False),
            }

        # cp_05: Extract
        elif cp_id == "cp_05":
            box_size = params.get("box_size") or 320
            bin_size = params.get("bin_size") or min(box_size // 2, 120)
            job_params = {
                "compute_num_gpus": _param(params.get("extract_gpus", 4), locked=True, visible=True, flagged=False),
                "box_size_pix": _param(box_size, locked=False, visible=True, flagged=True),
                "bin_size_pix": _param(bin_size, locked=False, visible=True, flagged=False),
                "output_f16": _param(True, locked=True, visible=True, flagged=False),
            }

        # cp_06: 2D Classification
        elif cp_id == "cp_06":
            _diameter_2d = params.get("particle_diameter") or 150
            job_params = {
                "class2D_K": _param(params.get("class2d_num_classes", 100), locked=False, visible=True, flagged=True),
                "class2D_max_res": _param(5, locked=False, visible=True, flagged=False),
                "class2D_window_inner_A": _param(_diameter_2d, locked=False, visible=True, flagged=False),
                "class2D_sigma_init_factor": _param(3, locked=True, visible=True, flagged=False),
                "class2D_num_full_iter_batch": _param(40, locked=False, visible=True, flagged=False),
                "compute_num_gpus": _param(params.get("class2d_gpus", 4), locked=True, visible=True, flagged=False),
                "compute_use_ssd": _param(False, locked=False, visible=True, flagged=False),
            }

        # cp_07: Ab-Initio
        elif cp_id == "cp_07":
            job_params = {
                "abinit_K": _param(params.get("abinit_num_classes", 3), locked=False, visible=True, flagged=True),
                "abinit_max_res": _param(10, locked=False, visible=True, flagged=False),
                "compute_use_ssd": _param(False, locked=False, visible=True, flagged=False),
            }

        # cp_08: Hetero Refine
        elif cp_id == "cp_08":
            job_params = {
                "multirefine_N": _param(params.get("box_size", 320), locked=False, visible=True, flagged=False),
                "multirefine_res_align_max": _param(3, locked=False, visible=True, flagged=False),
                "compute_use_ssd": _param(False, locked=False, visible=True, flagged=False),
            }

        # cp_09: Homogeneous Refine
        elif cp_id == "cp_09":
            job_params = {
                "refine_res_align_max": _param(3, locked=False, visible=True, flagged=False),
                "compute_use_ssd": _param(False, locked=False, visible=True, flagged=False),
            }

        # cp_09b: Nonuniform Refine
        elif cp_id == "cp_09b":
            job_params = {
                "refine_res_align_max": _param(3, locked=False, visible=True, flagged=False),
                "compute_use_ssd": _param(False, locked=False, visible=True, flagged=False),
            }

        # cp_10: CTF Refinement
        elif cp_id == "cp_10":
            job_params = {}

        # cp_11: Sharpen
        elif cp_id == "cp_11":
            job_params = {}

        # cp_12: Local Resolution
        elif cp_id == "cp_12":
            job_params = {}

        # --- 辅助 job ---

        # cp_01b: Import Micrographs（RELION接力）
        elif cp_id == "cp_01b":
            job_params = {
                "blob_paths": _param(params.get("micrographs_path"), locked=False, visible=True, flagged=True),
                "psize_A": _param(params.get("pixel_size", 0.96), locked=False, visible=True, flagged=True),
                "accel_kv": _param(params.get("voltage", 300), locked=False, visible=True, flagged=False),
                "cs_mm": _param(params.get("Cs", 2.7), locked=False, visible=True, flagged=False),
                "total_dose_e_per_A2": _param(params.get("total_dose", 50), locked=False, visible=True, flagged=False),
            }

        # cp_03b: Curate Exposures
        elif cp_id == "cp_03b":
            job_params = {}  # 人工筛选，无需参数

        # cp_03c: Denoise Train
        elif cp_id == "cp_03c":
            job_params = {
                "compute_num_cpus": _param(16, locked=True, visible=True, flagged=False),
            }

        # cp_04b: Template Picker
        elif cp_id == "cp_04b":
            _diameter_tmpl = params.get("particle_diameter") or 220
            job_params = {
                "diameter": _param(_diameter_tmpl, locked=False, visible=True, flagged=True),
                "max_num_hits": _param(params.get("max_num_hits", 300), locked=False, visible=True, flagged=False),
                "lowpass_res_template": _param(40, locked=False, visible=True, flagged=False),
                "lowpass_res": _param(30, locked=False, visible=True, flagged=False),
            }

        # cp_04c: Inspect Picks
        elif cp_id == "cp_04c":
            job_params = {}  # 人工检查，无需参数

        # cp_06b: Select 2D
        elif cp_id == "cp_06b":
            job_params = {}  # 人工筛选，无需参数

        jobs[job_id] = {
            "title": "",
            "description": "",
            "jobType": job_type,
            "groups": groups,
            "individualResults": [],
            "parameters": job_params,
        }

    # 组装 Workflow 对象（CryoSPARC 官方格式）
    workflow_json = {
        "_id": uuid.uuid4().hex[:24],  # 24位16进制字符串
        "category": "Default",
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",  # 毫秒精度，无时区
        "createdBy": "",  # 不携带任何来源账号标识，由目标 cryoSPARC 实例接管
        "csVersion": "v4.7.1",  # 使用最新版本号
        "description": (
            f"Generated by StructPilot v6.0. "
            f"Steps: {len(jobs)}. "
            f"Params: pixel_size={params.get('pixel_size')}A, "
            f"voltage={params.get('voltage')}kV, "
            f"Cs={params.get('Cs')}mm."
        ),
        "jobs": jobs,
        "parents": {},
        "title": workflow_name,
        "workflowVersion": "1.0.0",
    }

    return workflow_json


def workflow_to_json_str(workflow_json: dict, indent: int = 2) -> str:
    """序列化为 JSON 字符串。"""
    return json.dumps(workflow_json, ensure_ascii=False, indent=indent)
